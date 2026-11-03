"""S04-01B: crash-replay snapshot for startup installation only.

Copies local artifacts into a sibling recovery directory BEFORE any live
installation. A verified interrupted installation can restore these temporary
files, then normal startup MUST fetch/verify and apply Git MAIN. This is not a
publication path and cannot authorize local data as source of truth.
"""
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path


class InterruptedInstallError(RuntimeError):
    pass


def _sha(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _files(path):
    if path.is_symlink():
        raise InterruptedInstallError("Symlink is not permitted in startup recovery.")
    if path.is_file():
        return [path]
    if path.is_dir():
        all_files = []
        for item in sorted(path.rglob("*")):
            if item.is_symlink():
                raise InterruptedInstallError("Symlink is not permitted in startup recovery.")
            if item.is_file():
                all_files.append(item)
        return all_files
    return []


def _copy_and_sync(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as a, dest.open("xb") as b:
        shutil.copyfileobj(a, b, 1024 * 1024)
        b.flush()
        os.fsync(b.fileno())


def capture_before_install(marker, targets, accepted_oid):
    """Write immutable checked copies; install marker is written last."""
    marker = Path(marker)
    if marker.exists():
        raise InterruptedInstallError("A previous startup install remains pending.")
    token = uuid.uuid4().hex
    folder = marker.parent / "startup-replay" / token
    folder.mkdir(parents=True, exist_ok=False)
    inventory = []
    for index, (label, target) in enumerate(targets):
        target = Path(target)
        if target.is_symlink():
            raise InterruptedInstallError("Symlink in startup workspace.")
        target = target.resolve()
        kind = "directory" if target.is_dir() else "file" if target.is_file() else "missing"
        saved = folder / str(index)
        hashes = {}
        if kind != "missing":
            saved.mkdir()
            for item in _files(target):
                rel = item.relative_to(target).as_posix() if kind == "directory" else "__file__"
                copied = saved / rel
                _copy_and_sync(item, copied)
                original_hash = _sha(item)
                if _sha(copied) != original_hash:
                    raise InterruptedInstallError("Startup snapshot changed during capture.")
                hashes[rel] = original_hash
        inventory.append({"label": label, "target": str(target), "kind": kind, "hashes": hashes})
    document = {"format": 2, "transaction_id": token, "state": "INSTALL_PENDING",
                "git_main_oid": accepted_oid, "inventory": inventory}
    temporary = marker.with_name(marker.name + "." + token + ".tmp")
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        if marker.exists():
            raise InterruptedInstallError("Concurrent startup install detected.")
        os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)
    return folder


def recover_interrupted_install(marker, targets):
    """Verify complete saved set BEFORE modifying any live artifact.

    Copies backups to temporary siblings and replaces live files. Replay is
    idempotent if interrupted. Marker is removed only after all restores finish.
    """
    marker = Path(marker)
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
        expected = [(name, str(Path(path).resolve())) for name, path in targets]
        entries = document["inventory"]
        if (document["format"] != 2 or document["state"] != "INSTALL_PENDING"
                or len(entries) != len(expected) or
                [(x["label"], x["target"]) for x in entries] != expected):
            raise InterruptedInstallError("Startup recovery inventory does not match runtime.")
        token = document["transaction_id"]
        if not isinstance(token, str) or len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
            raise InterruptedInstallError("Startup recovery token is invalid.")
        folder = marker.parent / "startup-replay" / token
        for index, item in enumerate(entries):
            if item["kind"] not in {"directory", "file", "missing"}:
                raise InterruptedInstallError("Invalid saved artifact kind.")
            hashes = item["hashes"]
            saved = folder / str(index)
            actual = {}
            if item["kind"] != "missing":
                if not saved.is_dir():
                    raise InterruptedInstallError("Saved startup artifact is missing.")
                for item_path in _files(saved):
                    actual[item_path.relative_to(saved).as_posix()] = _sha(item_path)
            if hashes != actual:
                raise InterruptedInstallError("Saved startup artifact failed checksum verification.")
    except Exception as exc:
        raise InterruptedInstallError("Startup recovery inventory cannot be verified.") from exc

    # No data is written until all backups pass integrity checks.
    for index, (_, target_name) in enumerate(expected):
        entry = entries[index]
        target = Path(target_name)
        saved = folder / str(index)
        if entry["kind"] == "missing":
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            continue
        temporary = target.with_name("." + target.name + ".recover-" + token)
        if temporary.exists():
            if temporary.is_dir():
                shutil.rmtree(temporary)
            else:
                temporary.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["kind"] == "directory":
            shutil.copytree(saved, temporary)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            os.replace(temporary, target)
        else:
            _copy_and_sync(saved / "__file__", temporary)
            if target.is_dir():
                shutil.rmtree(target)
            os.replace(temporary, target)
    # Complete replay removes only the marker, not backups: retain evidence.
    marker.unlink()
    return document["git_main_oid"]
