"""Tamper-evident RV-02 publication receipts, only after verified Git MAIN.

A receipt proves the already-verified journal session was accepted at the
specified remote MAIN commit; it never independently validates Git or grants
WRITE authority. Missing receipt must not be interpreted as failed publication.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from centermanager.platform.write_recovery import _json

_SHA = re.compile(r"^[0-9a-fA-F]{40,64}$")
_SESSION = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class InvalidPublicationReceipt(ValueError):
    pass


def _body(*, session_id: str, base_main_oid: str, published_oid: str, verified_at: str) -> dict:
    return {
        "format": 1,
        "write_session_id": session_id,
        "base_main_oid": base_main_oid.lower(),
        "published_oid": published_oid.lower(),
        "verified_at_utc": verified_at,
    }


def _sign(body: dict, key: bytes) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()


def read_verified_receipt(path: Path, *, signing_key: bytes) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    signature = doc.pop("hmac_sha256", None)
    if not isinstance(signature, str) or not hmac.compare_digest(signature, _sign(doc, signing_key)):
        raise InvalidPublicationReceipt("Publication receipt is not authenticated")
    return doc


def record_verified_publication(document: dict, *, recovery_root: Path, signing_key: bytes) -> Path:
    """Write a durable signed receipt for one session after journal.published.

    This method performs no Git calls and does not modify SQLCipher or journal.
    """
    if not signing_key or len(signing_key) < 16:
        raise InvalidPublicationReceipt("A protected workspace signing key is required")
    sid = document.get("session_id", "")
    base = document.get("base_main_oid", "")
    oid = document.get("published_oid", "")
    if (document.get("status") != "PUBLISHED"
            or document.get("publication") != "VERIFIED"
            or sid in {".", ".."} or not _SESSION.fullmatch(sid)
            or not _SHA.fullmatch(base) or not _SHA.fullmatch(oid)):
        raise InvalidPublicationReceipt("A verified PUBLISHED journal receipt is required")
    directory = Path(recovery_root) / "rv02-published-main"
    target = directory / (sid + ".json")
    if target.exists():
        prior = read_verified_receipt(target, signing_key=signing_key)
        if (prior.get("published_oid") != oid.lower()
                or prior.get("base_main_oid") != base.lower()
                or prior.get("write_session_id") != sid):
            raise InvalidPublicationReceipt("Immutable publication receipt conflicts with verified Git MAIN")
        return target
    body = _body(
        session_id=sid, base_main_oid=base, published_oid=oid,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )
    _json(target, {**body, "hmac_sha256": _sign(body, signing_key)})
    return target
