"""Read-only finance voucher export, with verified portable ZIP packaging.

CSV contains voucher metadata. ZIP includes the CSV and exact PDF/image bytes.
No local absolute paths, database schema changes or WRITE authority.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import tempfile
import zipfile

from centermanager.core.paths import get_paths


def _safe_cell(value: str) -> str:
    value = " ".join(str(value or "").splitlines()).strip()
    if value.lstrip().startswith(("=", "+", "-", "@")):
        value = "'" + value
    return value


def voucher_csv_fields(attachments) -> tuple[int, str, str]:
    rows = list(attachments)
    return (
        len(rows),
        " | ".join(_safe_cell(a.original_filename) for a in rows),
        " | ".join(str(a.sha256 or "") for a in rows),
    )


def _voucher_path(item) -> Path:
    root = get_paths().attachment_dir
    relative = Path(item.stored_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Unsafe voucher storage path")
    for parent in (root, root.parent / "repository" / "Attachments"):
        candidate = parent / relative
        if candidate.is_file() and not candidate.is_symlink():
            if not candidate.resolve().is_relative_to(parent.resolve()):
                raise ValueError("Voucher path escapes trusted root")
            return candidate
    raise FileNotFoundError("Voucher file missing; cannot create complete ZIP")


def write_voucher_zip(destination, csv_text, entity_type, rows_by_id) -> None:
    """Write a complete ZIP atomically; missing/tampered voucher aborts export."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".voucher_export_", suffix=".zip",
                                     dir=str(destination.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("transactions.csv", "\ufeff" + csv_text)
            for entity_id, attachments in sorted(rows_by_id.items()):
                for item in attachments:
                    path = _voucher_path(item)
                    digest = hashlib.sha256()
                    filename = Path(str(item.original_filename).replace("\\", "/")).name
                    filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
                    if filename in ("", ".", ".."):
                        filename = "voucher"
                    arcname = f"vouchers/{entity_type}_{entity_id}/{item.id}_{filename}"
                    with path.open("rb") as stream, archive.open(arcname, "w") as target:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                            target.write(chunk)
                    if digest.hexdigest().lower() != str(item.sha256).lower():
                        raise ValueError("Voucher checksum mismatch; ZIP export aborted")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def csv_transaction_ids(csv_text: str) -> list[int]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return [int(row["Transaction ID"]) for row in reader]
