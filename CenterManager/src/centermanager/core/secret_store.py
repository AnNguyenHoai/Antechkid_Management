# -*- coding: utf-8 -*-
"""Windows-bound secret protection for CenterManager runtime credentials.

New production secrets are protected with Windows DPAPI and therefore cannot be
recovered from the application source code alone.  The module intentionally
contains no application-wide encryption key.
"""

import base64
import ctypes
import os
from ctypes import wintypes


_DPAPI_PREFIX = "DPAPI:v2:"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class SecretStoreUnavailable(RuntimeError):
    pass


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def is_available() -> bool:
    return os.name == "nt"


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_secret(plaintext: str) -> str:
    if not is_available():
        raise SecretStoreUnavailable("Windows DPAPI is unavailable on this platform")

    in_blob, in_buffer = _blob(plaintext.encode("utf-8"))
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return _DPAPI_PREFIX + base64.b64encode(protected).decode("ascii")
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
        del in_buffer


def unprotect_secret(bundle: str) -> str:
    if not bundle.startswith(_DPAPI_PREFIX):
        raise ValueError("Invalid DPAPI secret bundle")
    if not is_available():
        raise SecretStoreUnavailable("Windows DPAPI is unavailable on this platform")

    try:
        protected = base64.b64decode(bundle[len(_DPAPI_PREFIX):], validate=True)
    except Exception as exc:
        raise ValueError("Invalid DPAPI secret payload") from exc

    in_blob, in_buffer = _blob(protected)
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    ):
        raise ValueError("DPAPI could not decrypt this secret on the current Windows user/machine")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
        del in_buffer
