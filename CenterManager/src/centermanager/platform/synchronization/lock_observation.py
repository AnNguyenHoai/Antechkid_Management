"""Typed observations of remote authority. UNKNOWN never means available."""
from datetime import datetime, timedelta
from enum import Enum


class RemoteLockState(str, Enum):
    ACTIVE = "ACTIVE"
    GRACE = "GRACE"
    RECLAIMABLE = "RECLAIMABLE"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


def unknown_lock(error):
    return {
        "state": RemoteLockState.UNKNOWN.value, "verified": False,
        "locked": True, "owner": None, "session_id": None,
        "error": str(error), "oid": None,
    }


def observe_lock(data, *, oid=None, now=None, tolerance_seconds=600):
    """Validate the record before classifying time; preserve naive time policy.

    Only a successful ref read returning no ref, or an explicit unlocked record,
    establishes ABSENT. Invalid JSON/expiry/session must not become reclaimable.
    """
    if not isinstance(data, dict) or type(data.get("locked")) is not bool:
        return unknown_lock("Remote lock record is invalid or unreadable.")
    result = dict(data, oid=oid, verified=True, error=None)
    if not data["locked"]:
        result["state"] = RemoteLockState.ABSENT.value
        return result
    try:
        if not isinstance(data.get("session_id"), str) or not data["session_id"].strip():
            raise ValueError("missing session identity")
        for field in ("owner", "username"):
            value = data.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"invalid {field}")
        owner = data.get("owner") or data.get("username")
        if not owner or not owner.strip():
            raise ValueError("missing owner")
        if data.get("username") and data["username"] != owner:
            raise ValueError("owner identity mismatch")
        for field in ("lease_revision", "lock_generation"):
            value = data.get(field, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f"invalid {field}")
        expires = datetime.fromisoformat(data["lease_expires_at"])
        current = now or datetime.now()
        if current < expires:
            state = RemoteLockState.ACTIVE
        elif current < expires + timedelta(seconds=tolerance_seconds):
            state = RemoteLockState.GRACE
        else:
            state = RemoteLockState.RECLAIMABLE
        result["state"] = state.value
        return result
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return unknown_lock(f"Remote lock cannot be verified: {exc}")
