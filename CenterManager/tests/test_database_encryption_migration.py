# -*- coding: utf-8 -*-
import sqlite3

import pytest

from centermanager.database.encryption import apply_sqlcipher_key, load_sqlcipher_driver
from centermanager.database.encryption_migration import (
    encrypt_plaintext_database_in_place,
)


def test_plaintext_database_is_replaced_by_sqlcipher_and_preserves_data(tmp_path):
    pytest.importorskip("sqlcipher3")
    db_path = tmp_path / "center.db"
    plain = sqlite3.connect(db_path)
    plain.execute("PRAGMA user_version = 7")
    plain.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    plain.execute("INSERT INTO students(name) VALUES (?)", ("Sensitive Student Name",))
    plain.commit()
    plain.close()

    assert db_path.read_bytes().startswith(b"SQLite format 3\x00")

    key = bytes(range(32))
    encrypt_plaintext_database_in_place(db_path, key)

    raw = db_path.read_bytes()
    assert not raw.startswith(b"SQLite format 3\x00")
    assert b"Sensitive Student Name" not in raw

    with pytest.raises(sqlite3.DatabaseError):
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("SELECT name FROM students").fetchall()
        finally:
            connection.close()

    sqlcipher = load_sqlcipher_driver()
    encrypted = sqlcipher.connect(str(db_path))
    try:
        apply_sqlcipher_key(encrypted, key)
        assert encrypted.execute("PRAGMA user_version").fetchone()[0] == 7
        assert encrypted.execute("SELECT name FROM students").fetchone()[0] == "Sensitive Student Name"
    finally:
        encrypted.close()


def test_migration_is_idempotent_for_database_already_encrypted_with_same_key(tmp_path):
    pytest.importorskip("sqlcipher3")
    db_path = tmp_path / "center.db"
    sqlcipher = load_sqlcipher_driver()
    key = b"k" * 32
    connection = sqlcipher.connect(str(db_path))
    try:
        apply_sqlcipher_key(connection, key)
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker(value) VALUES ('ok')")
        connection.commit()
    finally:
        connection.close()

    result = encrypt_plaintext_database_in_place(db_path, key)
    assert result == db_path.resolve()

    connection = sqlcipher.connect(str(db_path))
    try:
        apply_sqlcipher_key(connection, key)
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "ok"
    finally:
        connection.close()
