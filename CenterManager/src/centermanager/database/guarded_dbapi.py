"""Driver-level statement/commit fencing for SQLite and SQLCipher runtime DBs.

Reinstall the native authorizer per execution to defeat prepared-statement cache
reuse. It sees CTE DML, triggers and bulk operations without parsing SQL text.
The process gate serializes admission/commit with lease-loss notification.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sqlite3
import uuid

from centermanager.database.mutation_authority import gate_for, MutationAuthorityError
from centermanager.database.mutation_permissions import mutation_permissions

_DML = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
_DDL = {getattr(sqlite3, name) for name in (
    'SQLITE_CREATE_INDEX', 'SQLITE_CREATE_TABLE', 'SQLITE_CREATE_TEMP_INDEX',
    'SQLITE_CREATE_TEMP_TABLE', 'SQLITE_CREATE_TEMP_TRIGGER', 'SQLITE_CREATE_TEMP_VIEW',
    'SQLITE_CREATE_TRIGGER', 'SQLITE_CREATE_VIEW', 'SQLITE_DROP_INDEX', 'SQLITE_DROP_TABLE',
    'SQLITE_DROP_TEMP_INDEX', 'SQLITE_DROP_TEMP_TABLE', 'SQLITE_DROP_TEMP_TRIGGER',
    'SQLITE_DROP_TEMP_VIEW', 'SQLITE_DROP_TRIGGER', 'SQLITE_DROP_VIEW', 'SQLITE_ALTER_TABLE',
    'SQLITE_REINDEX', 'SQLITE_ANALYZE', 'SQLITE_CREATE_VTABLE', 'SQLITE_DROP_VTABLE')}
_READ_PRAGMAS_WITH_ARGUMENT = {'table_info', 'table_xinfo', 'index_info', 'index_xinfo',
                             'index_list', 'foreign_key_list', 'integrity_check', 'quick_check',
                             'foreign_key_check'}


class GuardedConnection:
    def __init__(self, raw, path):
        self._raw = raw
        self._native_registry_id = id(raw)
        self._gate = gate_for(path)
        self._permits = {}
        self._statement_checks = set()
        self._denied = None
        self._receipt = None
        self._receipt_key = None
        self._statement_mutates = False
        self._incarnation = None

    def _require(self, category, permissions=()):
        key = (category, tuple(permissions))
        if key in self._statement_checks:
            self._statement_mutates = True
            return
        permit = self._gate.require(category, permissions, self._permits.get(key))
        if permit.actor_id != "system":
            if self._incarnation is not None and self._incarnation != permit.incarnation:
                raise MutationAuthorityError("Handle belongs to a retired WRITE session")
            self._incarnation = permit.incarnation
        self._permits[key] = permit
        self._statement_checks.add(key)
        self._statement_mutates = True

    def _validate_commit(self):
        for (category, permissions), permit in self._permits.items():
            self._gate.require(category, permissions, permit)

    def _authorizer(self, action, arg1, arg2, database, trigger):
        try:
            if action in _DDL:
                self._require('schema')
            elif action in _DML:
                # sqlite_master changes are also emitted by authorized DDL.
                if arg1 in {'sqlite_master', 'sqlite_temp_master', 'sqlite_schema'}:
                    self._require('schema')
                else:
                    from centermanager.database.mutation_authority import _local
                    maintenance = getattr(_local, 'maintenance', None)
                    if (maintenance is not None and maintenance[3] == 'bootstrap'
                            and arg1 not in {'users', 'roles', 'permissions', 'role_permissions'}):
                        raise MutationAuthorityError('Bootstrap permit only covers initial account seeding')
                    from centermanager.core.current_user import get_current_user
                    actor = get_current_user()
                    self_password = (arg1 == 'users' and action == sqlite3.SQLITE_UPDATE
                                     and arg2 in {'password_hash', 'force_password_change', 'login_attempts', 'locked_until'}
                                     and actor is not None
                                     and getattr(_local, 'password_user_id', None) == str(actor.id))
                    self_employee = (arg1 == 'employees' and action == sqlite3.SQLITE_INSERT
                                     and actor is not None
                                     and getattr(_local, 'employee_user_id', None) == str(actor.id))
                    permissions = (('self_password_change',) if self_password else
                                   ('self_employee_link',) if self_employee else
                                   mutation_permissions(arg1, action, arg2))
                    self._require('business', permissions)
            elif action in {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}:
                raise MutationAuthorityError('ATTACH/DETACH is not supported on runtime handles')
            elif action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in {'load_extension', 'sqlcipher_export', 'writefile'}:
                raise MutationAuthorityError('Mutating SQL extension functions are disabled')
            elif action == sqlite3.SQLITE_PRAGMA:
                name = str(arg1).lower()
                if name == 'wal_checkpoint':
                    self._require('checkpoint')
                elif name == 'foreign_keys' and str(arg2).upper() in {'ON', '1'}:
                    pass  # Per-connection safety, never persistent business data.
                elif arg2 is not None and name not in _READ_PRAGMAS_WITH_ARGUMENT:
                    self._require('pragma')
                elif name in {'optimize', 'incremental_vacuum', 'writable_schema', 'key', 'rekey'}:
                    self._require('pragma')
            elif action == sqlite3.SQLITE_TRANSACTION and arg1 == 'COMMIT':
                self._validate_commit()
            elif action == sqlite3.SQLITE_SAVEPOINT and arg1 == 'RELEASE':
                self._validate_commit()
            return sqlite3.SQLITE_OK
        except Exception as exc:
            self._denied = exc
            return sqlite3.SQLITE_DENY

    def _record(self, payload):
        # Preserve already admitted, uncommitted intentions independently of a
        # caller's subsequent rollback/close. Ciphertext only, no automatic replay.
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
        if self._receipt is None:
            from centermanager.platform.write_recovery import WriteRecoveryJournal
            root = WriteRecoveryJournal().root / 'mutation-intents'
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._receipt = root / (uuid.uuid4().hex + '.jsonl.enc')
            if database_encryption_required():
                self._receipt_key = DatabaseKeyStore().load()
            else:
                # Disposable plaintext/dev workspaces still receive encrypted receipts.
                key_path = root / 'local.key'
                if not key_path.exists():
                    with key_path.open('xb') as stream:
                        os.chmod(key_path, 0o600)
                        stream.write(os.urandom(32)); stream.flush(); os.fsync(stream.fileno())
                self._receipt_key = key_path.read_bytes()
        nonce = os.urandom(12)
        def encode(value):
            if isinstance(value, (bytes, bytearray, memoryview)):
                return {'bytes': base64.b64encode(bytes(value)).decode('ascii')}
            return {'type': type(value).__name__, 'value': str(value)}
        data = json.dumps(payload, default=encode).encode('utf-8')
        ciphertext = AESGCM(self._receipt_key).encrypt(nonce, data, b'CenterManager mutation intent v1')
        with self._receipt.open('ab') as stream:
            os.chmod(self._receipt, 0o600)
            stream.write(base64.b64encode(nonce + ciphertext) + b'\n')
            stream.flush(); os.fsync(stream.fileno())
        from centermanager.platform.write_recovery import _sync_dir
        _sync_dir(self._receipt.parent)

    def _execute(self, cursor, method, sql, parameters=()):
        with self._gate.lock:
            self._denied = None
            self._statement_mutates = False
            self._statement_checks.clear()
            # Called by the driver at prepare, before SQLite changes any page.
            # Record after prepare admission using a progress callback BEFORE
            # the first VM instruction, including cached statements.
            recorded = False
            def before_vm():
                nonlocal recorded
                if self._statement_mutates and not recorded and any(p.actor_id != "system" for p in self._permits.values()):
                    try:
                        self._record({'sql': sql, 'parameters': parameters,
                                      'session_id': self._gate.session_id,
                                      'incarnation': self._gate.incarnation,
                                      'repository_id': self._gate.repository_id,
                                      'database': str(self._gate.database)})
                        recorded = True
                    except Exception as exc:
                        self._denied = exc
                        try:
                            self._gate.invalidate("Mutation intent could not be persisted")
                        except Exception:
                            # The in-memory gate is already latched; a full disk
                            # may also prevent recording the protection marker.
                            pass
                        return 1
                return 0
            self._raw.set_authorizer(self._authorizer)
            self._raw.set_progress_handler(before_vm, 1)
            try:
                result = getattr(cursor, method)(sql, parameters)
                # Autocommit and explicit SQL COMMIT cannot carry permits forward.
                if not self._raw.in_transaction:
                    self._permits.clear()
                return result
            except Exception:
                if self._denied is not None:
                    raise MutationAuthorityError(str(self._denied)) from self._denied
                raise
            finally:
                self._raw.set_progress_handler(None, 0)

    @property
    def isolation_level(self):
        return self._raw.isolation_level

    @isolation_level.setter
    def isolation_level(self, value):
        if value is None:
            raise MutationAuthorityError('Runtime autocommit is unsupported; explicit fenced commit is required')
        self._raw.isolation_level = value

    def cursor(self, *args, **kwargs):
        return GuardedCursor(self, self._raw.cursor(*args, **kwargs))

    def execute(self, sql, parameters=()):
        cursor = self.cursor()
        return cursor.execute(sql, parameters)

    def executemany(self, sql, parameters):
        cursor = self.cursor()
        return cursor.executemany(sql, parameters)

    def executescript(self, script):
        raise MutationAuthorityError('Runtime executescript is unsupported; use fenced statements')

    def commit(self):
        with self._gate.lock:
            self._validate_commit()
            self._raw.commit()
            self._permits.clear()

    def rollback(self):
        with self._gate.lock:
            self._raw.rollback()
            self._permits.clear()

    def close(self):
        with self._gate.lock:
            self._raw.close()

    def backup(self, target, *args, **kwargs):
        if isinstance(target, GuardedConnection):
            raise MutationAuthorityError('Online backup into a live runtime handle is forbidden')
        return self._raw.backup(target, *args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()

    def create_function(self, name, num_params, func, **kwargs):
        if name not in {"regexp", "pow", "floor"}:
            raise MutationAuthorityError("Runtime SQL functions cannot be installed")
        return self._raw.create_function(name, num_params, func, **kwargs)

    def __getattr__(self, name):
        if name in {'set_authorizer', 'set_progress_handler', 'enable_load_extension', 'load_extension', 'deserialize', 'create_function', 'create_aggregate', 'create_window_function'}:
            raise MutationAuthorityError('Runtime authorization hooks cannot be replaced')
        return getattr(self._raw, name)


class GuardedCursor:
    def __init__(self, connection, raw):
        self.connection = connection
        self._raw = raw

    def execute(self, sql, parameters=()):
        self.connection._execute(self._raw, 'execute', sql, parameters)
        return self

    def executemany(self, sql, parameters):
        # A generator may execute arbitrary Python; capture it before locking.
        self.connection._execute(self._raw, 'executemany', sql, list(parameters))
        return self

    def executescript(self, script):
        return self.connection.executescript(script)

    def fetchone(self):
        with self.connection._gate.lock:
            if self.connection._permits:
                self.connection._validate_commit()
            return self._raw.fetchone()

    def fetchmany(self, *args):
        with self.connection._gate.lock:
            if self.connection._permits:
                self.connection._validate_commit()
            return self._raw.fetchmany(*args)

    def fetchall(self):
        with self.connection._gate.lock:
            if self.connection._permits:
                self.connection._validate_commit()
            return self._raw.fetchall()

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __getattr__(self, name):
        return getattr(self._raw, name)
