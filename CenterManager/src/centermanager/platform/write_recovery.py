"""Local preservation ledger. This is never a WRITE authority or a Git artifact.

No key, row content or raw remote URL belongs in this ledger. Unknown outcomes
remain pending. Recovery is explicit; this module never merges databases.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from pathlib import Path
import shutil
import subprocess
import uuid
from datetime import datetime, timezone

from centermanager.core.paths import get_paths
from centermanager.core.git_locator import locate_git


class RecoveryRequired(RuntimeError):
    pass


logger = logging.getLogger(__name__)

# TECH-011 (PO decision D-010): captures keep the newest N edit sessions plus
# every session whose final journal status is not CLEAN.
CAPTURE_RETENTION_SESSIONS = 20

# Content-addressed, never-rewritten finance vouchers: ``<sha256>.<ext>``.
# They are already versioned in Git, so captures reference them instead of
# copying them and fingerprints use size instead of re-reading the bytes.
_IMMUTABLE_ATTACHMENT_NAME = re.compile(r'^[0-9a-f]{64}\.(pdf|png|jpg|jpeg)$')


def _is_immutable_attachment(root_name, relative):
    parts = relative.split('/')
    if root_name == 'attachments':
        in_tree = len(parts) > 1 and parts[0] == 'Finance'
    elif root_name == 'repository':
        in_tree = len(parts) > 2 and parts[0] == 'Attachments' and parts[1] == 'Finance'
    else:
        in_tree = False
    return in_tree and bool(_IMMUTABLE_ATTACHMENT_NAME.match(parts[-1]))


def _excluded_from_capture(root_name, relative):
    """Files a capture does not copy (TECH-011).

    ``.git/objects`` content is excluded; the directory itself is kept so the
    captured repository still resolves HEAD/refs (``git rev-parse HEAD``).
    The captured working tree keeps every business file, including the DB.
    """
    if root_name == 'repository' and relative.startswith('.git/objects/'):
        return True
    return _is_immutable_attachment(root_name, relative)


def _capture_ignore(root_name, source):
    source = Path(source)

    def ignore(directory, names):
        base = Path(directory)
        ignored = []
        for child in names:
            relative = (base / child).relative_to(source).as_posix()
            if _excluded_from_capture(root_name, relative):
                ignored.append(child)
        return ignored
    return ignore


def _capture_hashes(root_name, root):
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): _hash(path)
        for path in root.rglob('*')
        if path.is_file() and not _excluded_from_capture(root_name, path.relative_to(root).as_posix())
    }


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sync_dir(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _install(source, target):
    if os.name == 'nt':
        # Atomic replacement with write-through, including the directory entry.
        import ctypes
        if not ctypes.windll.kernel32.MoveFileExW(str(source), str(target), 0x1 | 0x8):
            raise ctypes.WinError()
    else:
        os.replace(source, target)
        _sync_dir(target.parent)


def _json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        _install(temporary, path)
        _sync_dir(path.parent.parent)
    finally:
        temporary.unlink(missing_ok=True)


class WriteRecoveryJournal:
    def __init__(self, paths=None):
        self.paths = paths or get_paths()
        self.runtime = Path(self.paths.runtime_root).resolve()
        self.repository = self.runtime / 'repository'
        self.database = Path(self.paths.database_dir) / 'center.db'
        # Sibling survives runtime/metadata restoration and Git hard resets.
        self.root = self.runtime.with_name(self.runtime.name + '.write-recovery')
        self.journal = self.root / 'journal.json'

    def _git(self, *args):
        from centermanager.platform.synchronization._windows_subprocess import hidden_subprocess_kwargs
        executable = locate_git()
        if not executable:
            raise RecoveryRequired('Git is unavailable for local recovery inspection.')
        result = subprocess.run([str(executable), *args], cwd=self.repository,
                                capture_output=True, timeout=30,
                                **hidden_subprocess_kwargs())
        if result.returncode:
            # Do not include Git stderr: URLs / private file names may occur.
            raise RecoveryRequired('Local Git recovery inspection failed.')
        return result.stdout.decode('utf-8').strip()

    def _repository_id(self):
        # Hash the credential-free logical identity; never store a remote URL.
        return hashlib.sha256(self._git('config', '--get', 'remote.origin.url').encode()).hexdigest()

    def inspect(self):
        """Read metadata only; no Git fetch, DB open, checkpoint, pin or write."""
        if not self.journal.exists():
            return None
        try:
            document = json.loads(self.journal.read_text(encoding='utf-8'))
            if (document['format'] != 1 or document['runtime'] != str(self.runtime)
                    or document['status'] not in {'PREPARING', 'OPEN', 'PUBLISHING',
                    'PUBLISHED', 'POST_PUBLISH_PENDING', 'CLEAN', 'CANCELLED', 'RECONCILED'}):
                raise ValueError()
            return document
        except Exception as exc:
            raise RecoveryRequired('Recovery journal is unreadable. Keep the workspace and journal; inspect recovery before synchronizing.') from exc

    def _wal_pending(self):
        wal = self.database.with_name(self.database.name + '-wal')
        return wal.exists() and wal.stat().st_size > 0

    def assert_replaceable(self, *, legacy=False):
        document = self.inspect()
        if document is not None:
            if document.get('mutation_authority_lost') and document['status'] != 'RECONCILED':
                raise RecoveryRequired('WRITE authority was lost. Preserve local work and explicitly reconcile before synchronization.')
            if document['status'] == 'RECONCILED':
                # Explicit reconciliation permits only the exact preserved
                # workspace, not later mutations or an unrelated repository.
                current = self.fingerprint()
                previous = document['reconciled_fingerprint']
                runtime_equal = {k: v for k, v in current.items() if not k.startswith('repository/')} == {k: v for k, v in previous.items() if not k.startswith('repository/')}
                repository_replaced = (self._git('rev-parse', 'HEAD') == document['accepted_main_oid']
                                       and not self._git('status', '--porcelain', '--untracked-files=all'))
                if ((previous == current or (runtime_equal and repository_replaced))
                        and document['repository_id'] == self._repository_id()):
                    self.verify_capture(document['last_capture'])
                    return
            elif document['status'] in {'CLEAN', 'PUBLISHED'} and document.get('publication') == 'VERIFIED':
                if (self.database.is_file() and not self._wal_pending()
                        and document.get('published_runtime_sha256') == _hash(self.database)
                        and self._receipt_stable_files(document.get('accepted_local_files')) == self._receipt_stable_files(self._local_files())
                        and document['repository_id'] == self._repository_id()
                        and self._git('rev-parse', 'HEAD') in {document.get('published_oid'), self._git('rev-parse', '@{upstream}')}
                        and not self._git('status', '--porcelain', '--untracked-files=all')):
                    return
            # Do not weaken the refusal: emit a privacy-safe reason vector so
            # another handoff UI refresh failure can be diagnosed precisely.
            self.log_clean_mismatch('assert_replaceable', document)
            raise RecoveryRequired('Unpublished or uncertain WRITE data is protected. Stop synchronization; inspect and preserve recovery, then explicitly reconcile the saved base with accepted MAIN.')
        if legacy and not self.database.exists() and self.repository.exists():
            if not (self.repository / '.git').exists():
                if any(self.repository.iterdir()):
                    raise RecoveryRequired('Incomplete legacy repository may contain unpublished artifacts. Preserve before recloning.')
            elif (self._git('status', '--porcelain', '--untracked-files=all')
                    or self._git('rev-parse', 'HEAD') != self._git('rev-parse', '@{upstream}')):
                raise RecoveryRequired('Legacy Git artifacts may be unpublished although the runtime DB is absent. Preserve before resetting.')
        if legacy and self.database.exists():
            # Old clients have no durable receipt. Only exact equality with a
            # locally accepted Git artifact proves there is nothing to discard.
            repo_db = self.repository / 'database' / 'center.db'
            if (self._wal_pending() or not repo_db.is_file()
                    or _hash(self.database) != _hash(repo_db)
                    or self._git('status', '--porcelain', '--untracked-files=all')
                    or self._git('rev-parse', 'HEAD') != self._git('rev-parse', '@{upstream}')):
                raise RecoveryRequired('Legacy workspace has no recovery receipt and may contain local work. Preserve it and reconcile explicitly before synchronization.')

    def log_clean_mismatch(self, phase, document=None):
        """Log *which* accepted invariant changed without leaking business data.

        The receipt is never updated here. Diagnostics are best-effort; Git
        connectivity failures are reported as UNKNOWN, not mistaken for CLEAN.
        """
        try:
            document = self.inspect() if document is None else document
            if not isinstance(document, dict):
                logger.warning('Recovery mismatch phase=%s receipt=missing', phase)
                return
            current = self._local_files()
            expected = document.get('accepted_local_files') or {}
            current = self._receipt_stable_files(current)
            expected = self._receipt_stable_files(expected)
            added = set(current) - set(expected)
            removed = set(expected) - set(current)
            changed = {key for key in set(current) & set(expected)
                       if current[key] != expected[key]}
            # Do not log full paths: names can contain student identities.
            def categories(keys):
                return {category: sum(k.startswith(category + '/') for k in keys)
                        for category in ('database', 'metadata', 'attachments',
                                         'legacy-attachments', 'reports', 'exports')}
            db_match = self.database.is_file() and (
                _hash(self.database) == document.get('published_runtime_sha256'))
            wal_pending = self._wal_pending()
            repository_match = self._repository_id() == document.get('repository_id')
            head = self._git('rev-parse', 'HEAD')
            upstream = self._git('rev-parse', '@{upstream}')
            git_status_clean = not bool(
                self._git('status', '--porcelain', '--untracked-files=all'))
            from centermanager.platform.recovery_change_classification import classify_mismatch
            assessment = classify_mismatch(
                receipt_status=document.get('status'),
                publication=document.get('publication'),
                db_hash_match=db_match,
                wal_pending=wal_pending,
                local_files_match=not (added or removed or changed),
                git_clean=git_status_clean,
                repository_match=repository_match,
                head_accepted=(head == document.get('published_oid')),
                head_upstream=(head == upstream),
            )
            # Explicitly diagnose file/provenance drift, never claim that
            # a business row changed merely from a byte-level fingerprint.
            logger.warning(
                'Recovery classification phase=%s classification=%s reason=%s '
                'business_mutation_count=UNKNOWN',
                phase, assessment.classification, assessment.reason_code,
            )
            logger.warning(
                'Recovery mismatch phase=%s status=%s publication=%s '
                'db_hash_match=%s wal_pending=%s local_files_match=%s '
                'added=%s removed=%s changed=%s repository_match=%s '
                'head_accepted=%s head_upstream=%s git_clean=%s',
                phase, document.get('status'), document.get('publication'),
                db_match, wal_pending, not (added or removed or changed),
                categories(added), categories(removed), categories(changed),
                repository_match, head == document.get('published_oid'),
                head == upstream, git_status_clean,
            )
        except Exception as exc:
            logger.warning('Recovery mismatch phase=%s diagnostics_unknown=%s',
                           phase, type(exc).__name__)

    def begin_report_artifact_update(self):
        """Admit a rebuildable report operation, without resolving pending work."""
        document = self.inspect()
        if document is not None and document.get('mutation_authority_lost'):
            raise RecoveryRequired('Lost WRITE authority protects pending report artifacts until reconciliation.')
        if document is None or document['status'] == 'OPEN':
            return None
        if document['status'] == 'PUBLISHED':
            if self._wal_pending() or _hash(self.database) != document['published_runtime_sha256']:
                raise RecoveryRequired('Unaccepted local DB changes must be preserved before report regeneration.')
            return None  # Existing verified-release boundary still owns finalization.
        if document['status'] != 'CLEAN':
            raise RecoveryRequired('Pending recovery artifacts are protected; inspect and reconcile before regenerating reports.')
        self.assert_replaceable()
        return document

    def finish_report_artifact_update(self, before, report_paths):
        """Refresh only proven derived report bytes in an already CLEAN receipt.

        Never changes status, publication, base, authority or recovery captures.
        All DB/WAL, repository and unrelated-file checks remain fail-closed.
        """
        if before is None:
            return
        if self.inspect() != before:
            raise RecoveryRequired('Recovery state changed while rendering; report receipt was not accepted.')
        report_paths = tuple(Path(p).resolve() for p in report_paths)
        if (len(report_paths) != 2 or report_paths[0].suffix.lower() != '.pdf'
                or report_paths[1] != report_paths[0].with_suffix('.report.json')):
            raise RecoveryRequired('A derived update must identify one PDF and its matching report receipt.')
        allowed = set()
        for path in report_paths:
            path = Path(path).resolve()
            for name, folder in (('reports', self.runtime / 'Reports'), ('exports', self.runtime / 'Export')):
                if path.is_relative_to(folder.resolve()) and path.suffix.lower() in {'.pdf', '.json'}:
                    allowed.add(name + '/' + path.relative_to(folder.resolve()).as_posix())
                    break
            else:
                raise RecoveryRequired('Only derived report paths can refresh a clean local receipt.')
        current = self._local_files()
        previous = before['accepted_local_files']
        if ({k: v for k, v in self._receipt_stable_files(current).items() if k not in allowed} !=
                {k: v for k, v in self._receipt_stable_files(previous).items() if k not in allowed}
                or self._wal_pending()
                or _hash(self.database) != before['published_runtime_sha256']
                or self._repository_id() != before['repository_id']
                or self._git('rev-parse', 'HEAD') != before['published_oid']
                or self._git('status', '--porcelain', '--untracked-files=all')):
            raise RecoveryRequired('Unaccepted workspace changes remain protected; report rendering cannot clean them.')
        self.update(accepted_local_files=current)
        self.assert_replaceable()

    def begin(self, session_id, base_oid, authority):
        if not isinstance(session_id, str) or not session_id or not isinstance(base_oid, str) or not base_oid:
            raise RecoveryRequired('A verified session and accepted MAIN base are required before local editing.')
        self.assert_replaceable(legacy=True)
        if self._git('rev-parse', 'HEAD') != base_oid:
            raise RecoveryRequired('WRITE base does not match the materialized repository commit.')
        document = dict(format=1, session_id=session_id, base_main_oid=base_oid,
                        repository_id=self._repository_id(), runtime=str(self.runtime),
                        repository=str(self.repository), database=str(self.database),
                        created_at=datetime.now(timezone.utc).isoformat(), status='PREPARING',
                        authority=authority, ownership_epoch=None,
                        publication='UNVERIFIED', release='UNVERIFIED')
        # History is never garbage-collected here; no only-copy deletion.
        if self.journal.exists():
            _json(self.root / 'history' / (uuid.uuid4().hex + '.json'), self.inspect())
        _json(self.journal, document)
        self.preserve('base')
        self.update(status='OPEN')
        try:
            self.prune_captures()
        except Exception:
            # Retention is disk hygiene; it must never block editing.
            logger.exception('Recovery capture retention failed; captures retained')

    def prune_captures(self, keep_sessions=CAPTURE_RETENTION_SESSIONS):
        """Delete captures of old CLEAN sessions (TECH-011, PO decision D-010).

        Kept unconditionally: captures of the newest ``keep_sessions``
        sessions, of the current session, the journal's ``last_capture``,
        captures whose manifest/session cannot be read, and every capture of a
        session whose final journal status (from ``history/``) is not CLEAN.
        """
        captures_dir = self.root / 'captures'
        if not captures_dir.is_dir():
            return 0
        current = self.inspect() or {}
        current_session = current.get('session_id')
        last_capture = current.get('last_capture')
        last_capture = Path(last_capture).resolve() if last_capture else None
        final_status = {}
        history = self.root / 'history'
        if history.is_dir():
            for entry in history.glob('*.json'):
                try:
                    document = json.loads(entry.read_text(encoding='utf-8'))
                except Exception:
                    continue
                if isinstance(document, dict) and document.get('session_id'):
                    final_status[document['session_id']] = document.get('status')
        sessions = {}
        for capture in captures_dir.iterdir():
            if not capture.is_dir() or capture.is_symlink():
                continue
            try:
                manifest = json.loads((capture / 'manifest.json').read_text(encoding='utf-8'))
                session_id = (manifest.get('journal') or {}).get('session_id')
            except Exception:
                continue
            if not session_id:
                continue
            sessions.setdefault(session_id, []).append((capture.stat().st_mtime, capture))
        ordered = sorted(sessions, key=lambda sid: max(m for m, _ in sessions[sid]), reverse=True)
        recent = set(ordered[:keep_sessions])
        deleted = 0
        for session_id in ordered:
            if session_id in recent or session_id == current_session:
                continue
            if final_status.get(session_id) != 'CLEAN':
                continue
            for _, capture in sessions[session_id]:
                if last_capture is not None and capture.resolve() == last_capture:
                    continue
                shutil.rmtree(capture)
                deleted += 1
        if deleted:
            logger.info('Recovery capture retention removed %d capture(s) of CLEAN sessions', deleted)
        return deleted

    def update(self, **fields):
        document = self.inspect()
        if document is None:
            raise RecoveryRequired('Recovery journal is missing; local work remains blocked.')
        target = fields.get('status', document['status'])
        transitions = {
            'PREPARING': {'OPEN', 'RECONCILED'},
            'OPEN': {'PUBLISHING', 'CANCELLED', 'RECONCILED'},
            'PUBLISHING': {'PUBLISHED', 'CANCELLED', 'RECONCILED'},
            'PUBLISHED': {'CLEAN', 'POST_PUBLISH_PENDING', 'RECONCILED'},
            'POST_PUBLISH_PENDING': {'RECONCILED'},
            'CLEAN': {'RECONCILED'},
            'CANCELLED': {'RECONCILED'},
            'RECONCILED': {'CLEAN', 'RECONCILED'},
        }
        if target != document['status'] and target not in transitions[document['status']]:
            raise RecoveryRequired('Invalid recovery journal transition; preserve the workspace for review.')
        document.update(fields)
        _json(self.journal, document)

    def _workspace_roots(self):
        return {'repository': self.repository, 'database': self.database.parent,
                'metadata': self.paths.metadata_dir, 'attachments': self.paths.attachment_dir,
                'legacy-attachments': self.runtime / 'Attachments',
                'exports': getattr(self.paths, 'export_dir', self.runtime / 'Export'),
                'reports': getattr(self.paths, 'reports_dir', self.runtime / 'Reports')}

    @staticmethod
    def _receipt_stable_files(files):
        """Ignore only volatile SQLite sidecars when comparing CLEAN receipts.

        SQLite readers can create/remove the shared-memory index without any
        business mutation. WAL *contents* are NOT accepted by this exemption:
        callers separately require _wal_pending() == False, and the complete
        fingerprint/captures still preserve both sidecars.
        """
        return {k: v for k, v in (files or {}).items()
                if k not in {'database/center.db-shm', 'database/center.db-wal'}}

    def _local_files(self):
        return {k: v for k, v in self.fingerprint().items() if not k.startswith('repository/')}

    def fingerprint(self):
        """Hash all material that replacement/reset could destroy (including WAL)."""
        files = {}
        roots = self._workspace_roots()
        for name, root in roots.items():
            root = Path(root)
            if not root.exists():
                continue
            for path in sorted(root.rglob('*')):
                if path.is_symlink():
                    raise RecoveryRequired('Symlink in recovery workspace requires manual inspection.')
                if path.is_file():
                    relative = path.relative_to(root).as_posix()
                    if name == 'repository' and relative.startswith('.git/') and not (
                        relative in {'.git/HEAD', '.git/index', '.git/config', '.git/packed-refs'}
                        or relative.startswith('.git/refs/heads/')
                    ):
                        continue
                    if _is_immutable_attachment(name, relative):
                        # Content-addressed and never rewritten: the name is
                        # the SHA-256, so size detects truncation without
                        # re-reading every voucher on each write (QA-004 F3).
                        files[name + '/' + relative] = 'immutable:%d' % path.stat().st_size
                        continue
                    files[name + '/' + path.relative_to(root).as_posix()] = _hash(path)
        return files

    @staticmethod
    def _preservation_stable_files(name, files):
        """Only authoritative worktree and critical Git state must be stable.

        Git synchronization and lease renewal may update FETCH_HEAD, objects,
        reflogs, lock-main/queue-main refs and remote tracking refs *while* the
        post-publish recovery capture copies the repository. Those are Git
        transport/control-plane bytes, not a local business DB change.
        Copy and hash them into the capture, but do not let their concurrent
        churn trigger a spurious RECOVERY_REQUIRED after a verified MAIN push.

        HEAD, index, packed-refs, local business branches and all non-.git
        worktree files remain strictly checked. No paths outside the .git
        metadata namespace are exempted.
        """
        if name != 'repository':
            return files
        stable_git_paths = {'.git/HEAD', '.git/index', '.git/config', '.git/packed-refs'}
        def stable(path):
            if not path.startswith('.git/'):
                return True
            if path in stable_git_paths:
                return True
            if path.startswith('.git/refs/heads/'):
                return path not in {'.git/refs/heads/lock-main', '.git/refs/heads/queue-main'}
            return False
        return {path: digest for path, digest in files.items() if stable(path)}

    def preserve(self, reason):
        """Add a verified, immutable capture. Failure never changes the live DB."""
        from centermanager.database.wal_safety import runtime_database_publication_snapshot
        from centermanager.database.artifact_security import validate_database_artifact
        from centermanager.database.encryption import DatabaseKeyStore, database_encryption_required
        encrypted = database_encryption_required()
        store = DatabaseKeyStore()
        key = store.load() if encrypted else None
        capture = self.root / 'captures' / uuid.uuid4().hex
        capture.mkdir(parents=True, mode=0o700)
        # Keep partial captures after failure for diagnosis; never overwrite a
        # previous successful attempt. The manifest is installed last.
        with runtime_database_publication_snapshot() as snapshot:
            validate_database_artifact(snapshot, encryption_required=encrypted, key=key)
            shutil.copy2(snapshot, capture / 'center.db')
        validate_database_artifact(capture / 'center.db', encryption_required=encrypted, key=key)
        for name, source in self._workspace_roots().items():
            if name == 'database':
                continue  # Only the maintenance-fenced WAL-complete snapshot is authoritative.
            if Path(source).exists():
                source = Path(source)
                before = _capture_hashes(name, source)
                if any(p.is_symlink() for p in source.rglob('*')):
                    raise RecoveryRequired('Symlink requires manual preservation.')
                shutil.copytree(source, capture / name, ignore=_capture_ignore(name, source))
                after = _capture_hashes(name, source)
                copied = _capture_hashes(name, capture / name)
                stable_before = self._preservation_stable_files(name, before)
                stable_after = self._preservation_stable_files(name, after)
                stable_copied = self._preservation_stable_files(name, copied)
                if stable_before != stable_after or stable_before != stable_copied:
                    # Only hashed path labels are logged; never leak user data
                    # contents, remote URLs, database keys or file bytes.
                    mismatched = sorted(
                        path for path in (stable_before.keys() | stable_after.keys() | stable_copied.keys())
                        if not (stable_before.get(path) == stable_after.get(path) == stable_copied.get(path))
                    )
                    import logging
                    logging.getLogger(__name__).error(
                        "Preservation changed critical %s files: %s",
                        name, mismatched[:8],
                    )
                    raise RecoveryRequired('Workspace changed during preservation. Retain all copies; retry with CenterManager stopped.')
        if encrypted:
            # Existing user-bound DPAPI ciphertext only. Never export the key.
            shutil.copy2(store.bundle_path, capture / 'database_key.dpapi')
            pin = self.paths.config_dir / 'authoritative_database_identity.json'
            if pin.is_file():
                shutil.copy2(pin, capture / pin.name)
        hashes = {}
        for path in capture.rglob('*'):
            if path.is_symlink():
                raise RecoveryRequired('Cannot preserve a symlink as an authenticated capture.')
            if path.is_file():
                os.chmod(path, 0o600)
                with path.open('r+b') as stream:
                    os.fsync(stream.fileno())
                hashes[path.relative_to(capture).as_posix()] = _hash(path)
        if self._wal_pending() or _hash(self.database) != hashes['center.db']:
            raise RecoveryRequired('Runtime changed after the recovery snapshot. Keep all copies and retry with CenterManager stopped.')
        manifest = dict(format=1, reason=reason, files=hashes, encrypted=encrypted,
                        key_reference=str(store.bundle_path) if encrypted else None,
                        journal=self.inspect())
        if encrypted:
            manifest['hmac_sha256'] = hmac.new(key, b'antechkids-local-recovery-v1\0' + json.dumps(manifest, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        for directory in sorted((p for p in capture.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            _sync_dir(directory)
        _sync_dir(capture)
        _sync_dir(capture.parent)
        _json(capture / 'manifest.json', manifest)
        self.verify_capture(capture)
        if self.inspect() is not None:
            self.update(last_capture=str(capture))
        return capture

    def verify_capture(self, capture):
        capture = Path(capture).resolve()
        if capture.parent != (self.root / 'captures').resolve():
            raise RecoveryRequired('Recovery capture must belong to this workspace.')
        manifest = json.loads((capture / 'manifest.json').read_text(encoding='utf-8'))
        from centermanager.database.encryption import database_encryption_required
        if database_encryption_required() and not manifest.get('encrypted'):
            raise RecoveryRequired('An encrypted recovery manifest is required in production.')
        if manifest.get('encrypted'):
            from centermanager.database.encryption import DatabaseKeyStore
            key = DatabaseKeyStore(capture / 'database_key.dpapi').load()
            unsigned = {k: v for k, v in manifest.items() if k != 'hmac_sha256'}
            expected_signature = hmac.new(key, b'antechkids-local-recovery-v1\0' + json.dumps(unsigned, sort_keys=True).encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(manifest.get('hmac_sha256', ''), expected_signature):
                raise RecoveryRequired('Recovery manifest authentication failed. Keep all copies.')
        for relative, expected in manifest['files'].items():
            path = (capture / relative).resolve()
            if not path.is_relative_to(capture) or _hash(path) != expected:
                raise RecoveryRequired('Recovery capture verification failed. Retain all copies and retry preservation.')
        if not manifest['files'].get('center.db'):
            raise RecoveryRequired('Recovery capture has no database.')
        return manifest

    def published(self, provider):
        if self.inspect().get('mutation_authority_lost'):
            raise RecoveryRequired('Lost WRITE authority requires explicit reconciliation, not publication cleanup.')
        # A True return value alone is not publish acknowledgement. Require a
        # fresh remote observation equal to the actual local commit.
        local = provider.get_local_main_commit()
        remote = provider.observe_remote_main_commit()
        if not local or not remote or local != remote:
            raise RecoveryRequired('Publish outcome is UNKNOWN; local data remains protected.')
        capture = self.preserve('published')
        repo_db = self.repository / 'database' / 'center.db'
        if (_hash(capture / 'center.db') != _hash(repo_db)
                or self._git('hash-object', 'database/center.db') != self._git('rev-parse', 'HEAD:database/center.db')
                or self._git('status', '--porcelain', '--untracked-files=all')):
            raise RecoveryRequired('Runtime differs from the accepted publication. Keep recovery data for reconciliation.')
        self.update(status='PUBLISHED', publication='VERIFIED', published_oid=local,
                    published_runtime_sha256=_hash(capture / 'center.db'),
                    accepted_local_files=self._local_files())
        # RV-02: independent signed receipt AFTER the exact remote MAIN check.
        # A failed local receipt cannot undo a confirmed Git publication or
        # invent a new failed business transaction. Retain the journal proof.
        try:
            from centermanager.database.encryption import DatabaseKeyStore
            from centermanager.platform.recovery_publication_receipt import record_verified_publication
            record_verified_publication(
                self.inspect(), recovery_root=self.root,
                signing_key=DatabaseKeyStore().load(),
            )
        except Exception:
            logger.exception('Verified Git MAIN publish but RV-02 signed receipt is unavailable')

    def preserve_post_publish_changes(self):
        """A success callback may commit local report metadata after the push.

        It is unaccepted work even though the earlier publication was verified.
        Preserve it and require explicit review; never call it clean or push a
        second binary snapshot implicitly.
        """
        document = self.inspect()
        if not self._wal_pending() and _hash(self.database) == document['published_runtime_sha256']:
            return False
        self.preserve('post-publish-local-changes')
        self.update(status='POST_PUBLISH_PENDING')
        return True

    def released(self):
        document = self.inspect()
        if document.get('mutation_authority_lost'):
            self.update(release='VERIFIED')
            return
        fields = dict(release='VERIFIED', status='CLEAN' if document['status'] == 'PUBLISHED' else document['status'])
        if document['status'] == 'PUBLISHED':
            # Pending-version metadata may have been finalized after publish verification.
            if _hash(self.database) != document['published_runtime_sha256'] or self._wal_pending():
                raise RecoveryRequired('Runtime changed after publish; retain recovery for explicit review.')
            fields['accepted_local_files'] = self._local_files()
        self.update(**fields)

    def record_verified_fresh_install(self, *, provider, accepted_main):
        """Record the first receipt after this process installs and migrates MAIN.

        Caller must hold ephemeral fresh-install provenance from startup; this
        is not a repair mechanism for pre-existing or unaccepted local work.
        Migration is an authorized bootstrap operation, so the runtime DB
        need not have the same byte hash as the repository's pre-migration DB.
        """
        if self.journal.exists():
            raise RecoveryRequired('Existing WRITE journal cannot be replaced by fresh-install receipt.')
        if (not accepted_main or
                getattr(provider, '_fresh_install_main_oid', None) != accepted_main):
            raise RecoveryRequired('Fresh-install startup proof is unavailable.')
        if provider.observe_remote_main_commit() != accepted_main:
            raise RecoveryRequired('Git MAIN changed after startup; first WRITE remains blocked.')
        if (not self.database.is_file() or self._wal_pending() or
                self._git('rev-parse', 'HEAD') != accepted_main or
                self._git('rev-parse', '@{upstream}') != accepted_main or
                self._git('status', '--porcelain', '--untracked-files=all')):
            raise RecoveryRequired('Fresh-install runtime is not stable at its accepted MAIN base.')
        repo_db = self.repository / 'database' / 'center.db'
        if not repo_db.is_file():
            raise RecoveryRequired('Accepted MAIN has no repository database.')
        # Alembic migration has already completed and its physical schema has
        # been verified by ensure_schema(). No application user/editor exists.
        receipt = dict(
            format=1, runtime=str(self.runtime), repository=str(self.repository),
            database=str(self.database), repository_id=self._repository_id(),
            session_id='fresh-install-' + uuid.uuid4().hex,
            base_main_oid=accepted_main, published_oid=accepted_main,
            status='CLEAN', publication='VERIFIED', release='VERIFIED',
            published_runtime_sha256=_hash(self.database),
            accepted_local_files=self._local_files(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        _json(self.journal, receipt)
        # Receipt is now tied to exact runtime bytes; never leave the startup
        # capability available for a second bootstrap attempt.
        delattr(provider, '_fresh_install_main_oid')
        self.assert_replaceable()
        logger.info('Fresh-install WRITE recovery receipt initialized after schema migration')

    def record_verified_manual_reset(self, *, provider, accepted_main, archive):
        """Seal a NEW MAIN session only after old local evidence was archived.

        This is not a repair of the old journal. It is an independent receipt
        for a fully installed/migrated Git MAIN, checked before any login or
        WRITE. The previous journal survives unchanged inside the archive.
        """
        from centermanager.platform.sync.manual_review_backup import (
            verify_manual_review_backup,
        )
        archive = Path(archive).resolve()
        if (not archive.is_relative_to((self.root / 'manual-review').resolve())
                or not archive.is_dir()):
            raise RecoveryRequired('Manual Recovery backup is outside the protected archive.')
        verify_manual_review_backup(archive)
        if self.journal.exists() and not (archive / 'recovery' / 'journal.json').is_file():
            raise RecoveryRequired('Original Recovery journal was not preserved before MAIN reset.')
        if (not accepted_main
                or getattr(provider, '_verified_manual_main_oid', None) != accepted_main
                or str(archive) != getattr(provider, '_verified_manual_backup_path', None)
                or provider.observe_remote_main_commit() != accepted_main):
            raise RecoveryRequired('Independent MAIN verification is not available for manual reset.')
        if (not self.database.is_file() or self._wal_pending()
                or not (self.repository / 'database' / 'center.db').is_file()
                or self._git('rev-parse', 'HEAD') != accepted_main
                or self._git('rev-parse', '@{upstream}') != accepted_main
                or self._git('status', '--porcelain', '--untracked-files=all')):
            raise RecoveryRequired('Manual reset cannot attest the installed MAIN generation.')
        # The old raw journal is already copied and hashed in the archive.
        # Do not mutate its status to CLEAN or silently mark it reviewed.
        receipt = dict(
            format=1, runtime=str(self.runtime), repository=str(self.repository),
            database=str(self.database), repository_id=self._repository_id(),
            session_id='main-reset-' + uuid.uuid4().hex,
            base_main_oid=accepted_main, published_oid=accepted_main,
            status='CLEAN', publication='VERIFIED', release='VERIFIED',
            published_runtime_sha256=_hash(self.database),
            accepted_local_files=self._local_files(),
            manual_review_archive=str(archive),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        _json(self.journal, receipt)
        delattr(provider, '_verified_manual_main_oid')
        delattr(provider, '_verified_manual_backup_path')
        self.assert_replaceable()
        logger.warning('New Git MAIN receipt accepted; previous local Recovery remains archived for manual review')

    def refresh_verified_bootstrap_migration(self, *, provider, before):
        """Refresh a previously CLEAN receipt after authorized startup Alembic.

        The caller verified the receipt before ensure_schema() and runs this
        immediately afterwards, before login. No pending/legacy receipt may
        be promoted to CLEAN by this operation.
        """
        if (not isinstance(before, dict) or before.get('status') != 'CLEAN'
                or before.get('publication') != 'VERIFIED'
                or self.inspect() != before):
            raise RecoveryRequired('Bootstrap schema receipt changed or was never CLEAN.')
        oid = before.get('published_oid')
        if (not oid or provider.observe_remote_main_commit() != oid or
                self._git('rev-parse', 'HEAD') != oid or
                self._git('rev-parse', '@{upstream}') != oid or
                self._repository_id() != before.get('repository_id') or
                self._git('status', '--porcelain', '--untracked-files=all') or
                not self.database.is_file() or self._wal_pending()):
            raise RecoveryRequired('Cannot attest the authoritative schema migration.')
        updated_files = self._local_files()
        db_hash = _hash(self.database)
        if (before.get('published_runtime_sha256') != db_hash or
                before.get('accepted_local_files') != updated_files):
            self.update(
                published_runtime_sha256=db_hash,
                accepted_local_files=updated_files,
            )
            self.assert_replaceable()
            logger.info('Verified CLEAN receipt updated after bootstrap schema migration')

    def record_verified_handoff_install(self, *, before, accepted_main, observe_main):
        """Accept an authoritative MAIN install after its authorized Alembic migration.

        An already verified CLEAN receipt is required: this does not recover
        or accept any unpublished local editing. The new runtime may differ
        bytewise from repository/center.db only because the handoff installed
        that exact validated MAIN DB and migrated it under the maintenance
        permit. Call before deleting the old runtime/sidecar rollback copies.
        """
        if (not isinstance(before, dict)
                or before.get('status') != 'CLEAN'
                or before.get('publication') != 'VERIFIED'
                or self.inspect() != before):
            raise RecoveryRequired('WRITE handoff requires an unchanged, verified CLEAN receipt.')
        if not accepted_main or observe_main() != accepted_main:
            raise RecoveryRequired('Git MAIN changed or cannot be verified during WRITE handoff.')
        if (not self.database.is_file() or self._wal_pending()
                or not (self.repository / 'database' / 'center.db').is_file()
                or self._repository_id() != before.get('repository_id')
                or self._git('rev-parse', 'HEAD') != accepted_main
                or self._git('rev-parse', '@{upstream}') != accepted_main
                or self._git('status', '--porcelain', '--untracked-files=all')):
            raise RecoveryRequired('Installed WRITE handoff DB is not pinned to accepted Git MAIN.')
        # Commit the new attested checksum only after every acceptance check.
        # The caller retains the old runtime DB until this succeeds.
        old = before
        try:
            self.update(
                status='CLEAN', publication='VERIFIED',
                published_oid=accepted_main,
                published_runtime_sha256=_hash(self.database),
                accepted_local_files=self._local_files(),
            )
            self.assert_replaceable()
        except Exception:
            # Do not leave a receipt describing a DB that the caller will roll
            # back. Restore the pre-handoff receipt if this method wrote one.
            if self.inspect() != old:
                _json(self.journal, old)
            raise
        logger.info('WRITE handoff CLEAN receipt verified after authorized schema migration')

    def record_synchronized(self):
        """Refresh an existing verified/reconciled receipt after remote install.

        Never resolves an OPEN/UNKNOWN session, and never drops retained captures.
        """
        document = self.inspect()
        if document is None:
            return
        if document['status'] not in {'CLEAN', 'PUBLISHED', 'RECONCILED'}:
            raise RecoveryRequired('A pending journal cannot be marked synchronized.')
        repo_db = self.repository / 'database' / 'center.db'
        local = self._git('rev-parse', 'HEAD')
        if (local != self._git('rev-parse', '@{upstream}') or self._wal_pending()
                or _hash(self.database) != _hash(repo_db)):
            raise RecoveryRequired('Runtime does not match accepted MAIN; recovery remains blocked.')
        self.update(status='CLEAN', publication='VERIFIED', published_oid=local,
                    published_runtime_sha256=_hash(self.database), accepted_local_files=self._local_files())

    def reconcile(self, *, base_oid, accepted_main, observe_main):
        """Explicitly retain local work and permit subsequent remote replacement.

        No merging, publishing or authority acquisition. Call only with the app
        stopped, after inspecting base/local/current MAIN. The supplied MAIN must
        match a fresh remote observation; UNKNOWN always blocks.
        """
        document = self.inspect()
        if document is not None and document.get('base_main_oid') != base_oid:
            raise RecoveryRequired('Reconciliation base does not match the preserved session.')
        observed = observe_main()
        if not accepted_main or not observed or accepted_main != observed:
            raise RecoveryRequired('Accepted MAIN is unknown or changed. Reinspect before reconciliation.')
        capture = self.preserve('explicit-reconciliation')
        self.verify_capture(capture)
        if document is None:
            document = dict(format=1, runtime=str(self.runtime), base_main_oid=base_oid,
                            repository_id=self._repository_id(), status='CANCELLED')
            _json(self.journal, document)
        fingerprint = self.fingerprint()
        captured = self.verify_capture(capture)['files']['center.db']
        if self._wal_pending() or _hash(self.database) != captured:
            raise RecoveryRequired('Runtime changed during reconciliation; no replacement was authorized.')
        self.update(status='RECONCILED', mutation_authority_lost=False, accepted_main_oid=accepted_main,
                    last_capture=str(capture), reconciled_fingerprint=fingerprint)


def require_replaceable(*, legacy=False):
    WriteRecoveryJournal().assert_replaceable(legacy=legacy)


def require_database_replaceable(database_path):
    """Offline activation tools must honor the journal beside their target DB."""
    from types import SimpleNamespace
    path = Path(database_path).resolve()
    runtime = path.parent.parent
    paths = SimpleNamespace(runtime_root=runtime, database_dir=path.parent,
                            metadata_dir=runtime / 'metadata', attachment_dir=runtime / 'Attachment')
    WriteRecoveryJournal(paths).assert_replaceable()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Local WRITE recovery. Stop CenterManager before preservation or reconciliation.')
    parser.add_argument('action', choices=['inspect', 'preserve', 'reconcile'])
    parser.add_argument('--base', help='Preserved base MAIN OID reviewed by the operator')
    parser.add_argument('--main', help='Currently accepted MAIN OID reviewed by the operator')
    args = parser.parse_args()
    journal = WriteRecoveryJournal()
    try:
        if args.action == 'inspect':
            print(json.dumps(journal.inspect() or {'status': 'LEGACY_NO_JOURNAL'}, indent=2))
        elif args.action == 'preserve':
            print(journal.preserve('operator-request'))
        else:
            if not args.base or not args.main:
                parser.error('reconcile requires --base and --main; this retains local work and permits replacing it with reviewed MAIN')
            from centermanager.services.git_config_service import GitConfigService
            from centermanager.platform.synchronization import GitSynchronizationProvider
            config = GitConfigService().get_config()
            if config is None:
                raise RecoveryRequired('Git configuration is unavailable. No reconciliation was performed.')
            provider = GitSynchronizationProvider(repo_path=journal.repository,
                repository_url=config.repository_url, token=config.token,
                branch=config.branch, username=config.username,
                allow_local_file_remote=config.allow_local_file_remote)
            if not provider.connect():
                raise RecoveryRequired('Git observation unavailable. No reconciliation was performed.')
            journal.reconcile(base_oid=args.base, accepted_main=args.main,
                              observe_main=provider.observe_remote_main_commit)
            print('Local work retained. Explicit reconciliation recorded; normal startup may apply reviewed MAIN.')
    except Exception as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
