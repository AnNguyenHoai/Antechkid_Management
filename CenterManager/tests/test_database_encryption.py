# -*- coding: utf-8 -*-
import base64

import pytest

from centermanager.database import encryption


def _fake_protect(value: str) -> str:
    return "DPAPI:v2:" + value


def _fake_unprotect(value: str) -> str:
    assert value.startswith("DPAPI:v2:")
    return value[len("DPAPI:v2:"):]


def test_database_key_store_creates_and_reloads_same_256_bit_key(tmp_path, monkeypatch):
    monkeypatch.setattr(encryption, "protect_secret", _fake_protect)
    monkeypatch.setattr(encryption, "unprotect_secret", _fake_unprotect)
    bundle = tmp_path / "database_key.dpapi"
    store = encryption.DatabaseKeyStore(bundle)

    first = store.load_or_create(allow_create=True)
    second = store.load()

    assert len(first) == 32
    assert second == first
    text = bundle.read_text(encoding="utf-8")
    assert text.startswith("DBKEY:v1:DPAPI:v2:")
    assert first.hex() not in text
    assert base64.b64encode(first).decode("ascii") in text  # protected by fake DPAPI in this unit test


def test_database_key_store_fails_closed_when_key_missing(tmp_path):
    store = encryption.DatabaseKeyStore(tmp_path / "missing.dpapi")
    with pytest.raises(encryption.DatabaseKeyUnavailable, match="missing"):
        store.load_or_create(allow_create=False)


def test_database_key_store_rejects_invalid_key_length(tmp_path, monkeypatch):
    monkeypatch.setattr(encryption, "unprotect_secret", lambda value: base64.b64encode(b"short").decode("ascii"))
    bundle = tmp_path / "database_key.dpapi"
    bundle.write_text("DBKEY:v1:DPAPI:v2:payload", encoding="utf-8")

    with pytest.raises(encryption.DatabaseKeyUnavailable, match="length"):
        encryption.DatabaseKeyStore(bundle).load()


def test_apply_sqlcipher_key_verifies_cipher_version():
    statements = []

    class Cursor:
        def execute(self, statement):
            statements.append(statement)
            return self

        def fetchone(self):
            return ("4.7.0",)

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

    key = bytes(range(32))
    encryption.apply_sqlcipher_key(Connection(), key)

    assert statements[0].startswith("PRAGMA key =")
    assert key.hex() in statements[0]
    assert statements[1] == "PRAGMA cipher_version;"


def test_apply_sqlcipher_key_rejects_plain_sqlite_driver():
    class Cursor:
        def execute(self, statement):
            return self

        def fetchone(self):
            return None

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

    with pytest.raises(encryption.DatabaseEncryptionDriverUnavailable):
        encryption.apply_sqlcipher_key(Connection(), b"x" * 32)
