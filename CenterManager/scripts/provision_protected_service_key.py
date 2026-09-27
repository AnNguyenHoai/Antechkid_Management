# -*- coding: utf-8 -*-
"""Provision the SEC-02 protected service key bundle without exposing raw key text.

Run as an authorized administrator BEFORE service-only ACLs are applied. The tool
loads the existing user-scoped workspace key, re-wraps the same 256-bit key with
machine-scoped DPAPI into the protected Key directory, validates round-trip
unsealing, and never prints/logs the key material.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

from centermanager.database.encryption import DatabaseKeyStore
from centermanager.security.protected_storage import get_protected_storage_layout


class ProtectedKeyProvisioningError(RuntimeError):
    pass


def _is_windows_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def provision_service_key(*, overwrite: bool = False) -> Path:
    if sys.platform != "win32":
        raise ProtectedKeyProvisioningError("Protected service key provisioning is Windows-only.")
    if not _is_windows_admin():
        raise ProtectedKeyProvisioningError("Administrator privileges are required.")

    source_store = DatabaseKeyStore()
    source_key = source_store.load()

    layout = get_protected_storage_layout()
    target_store = DatabaseKeyStore(
        bundle_path=layout.key_bundle_path,
        machine_scope=True,
    )
    target_store.provision(source_key, overwrite=overwrite)
    round_trip = target_store.load()
    if round_trip != source_key:
        raise ProtectedKeyProvisioningError("Protected service key round-trip verification failed.")
    return layout.key_bundle_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re-wrap the existing workspace DB key for AnTechKidsData protected storage."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing protected service key bundle only after explicit authorization.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = provision_service_key(overwrite=args.overwrite)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Protected service key bundle provisioned: {path}")
    print("[OK] Raw SQLCipher key material was not emitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
