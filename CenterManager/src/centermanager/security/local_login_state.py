"""Per-workstation login throttling, never an authoritative users mutation.

Shared account activity/lock fields are still respected by PermissionService.
Local attempts cannot unlock a persisted account. Credentials and roles remain
exclusively in SQLCipher; this encrypted operational receipt grants no access.
"""
from datetime import datetime, timedelta
import base64
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from centermanager.core.paths import get_paths
from centermanager.database.encryption import DatabaseKeyStore

_lock = threading.RLock()


class LocalLoginState:
    def __init__(self, user, *, key=None):
        root = Path(get_paths().runtime_root)
        self.root = root.with_name(root.name + '.login-state')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / (hashlib.sha256(str(user.id).encode()).hexdigest() + '.enc')
        if key is None:
            from centermanager.database.encryption import database_encryption_required
            if database_encryption_required():
                key = DatabaseKeyStore().load()
            else:
                # Source/dev plaintext workspaces have no DPAPI workspace key.
                key_path = self.root / 'local.key'
                try:
                    with key_path.open('xb') as stream:
                        os.chmod(key_path, 0o600)
                        stream.write(os.urandom(32)); stream.flush(); os.fsync(stream.fileno())
                except FileExistsError:
                    pass
                key = key_path.read_bytes()
        self.key = key
        self.fingerprint = hashlib.sha256(user.password_hash.encode()).hexdigest()
        self.persisted_attempts = user.login_attempts or 0

    def _read(self):
        if not self.path.exists():
            return {'attempts': self.persisted_attempts, 'locked_until': None}
        value = base64.b64decode(self.path.read_bytes())
        result = json.loads(AESGCM(self.key).decrypt(value[:12], value[12:], b'CenterManager login v1'))
        if result['credential'] != self.fingerprint:
            return {'attempts': self.persisted_attempts, 'locked_until': None}
        return result

    def assert_unlocked(self):
        with _lock:
            state = self._read()
            if state.get('locked_until') and datetime.fromisoformat(state['locked_until']) > datetime.now():
                raise ValueError('Account is locked on this workstation. Please try again later.')

    def record(self, success):
        with _lock:
            state = self._read()
            count = 0 if success else state['attempts'] + 1
            state = {'credential': self.fingerprint, 'attempts': count,
                     'locked_until': (datetime.now() + timedelta(minutes=15)).isoformat() if count >= 5 else None,
                     'last_login': datetime.now().isoformat() if success else state.get('last_login')}
            nonce = os.urandom(12)
            value = nonce + AESGCM(self.key).encrypt(nonce, json.dumps(state).encode(), b'CenterManager login v1')
            temporary = self.path.with_name(uuid.uuid4().hex + '.tmp')
            try:
                with temporary.open('xb') as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(base64.b64encode(value)); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
            return count
