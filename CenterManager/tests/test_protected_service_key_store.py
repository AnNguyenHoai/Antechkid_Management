# -*- coding: utf-8 -*-
import base64

import centermanager.database.encryption as encryption
from centermanager.database.encryption import DatabaseKeyStore


def test_service_key_store_uses_machine_scope_without_changing_default(tmp_path, monkeypatch):
    calls = []

    def protect_user(value):
        calls.append(("user", value))
        return "USER:" + value

    def protect_machine(value):
        calls.append(("machine", value))
        return "MACHINE:" + value

    def unprotect(value):
        if value.startswith("MACHINE:"):
            return value[len("MACHINE:"):]
        if value.startswith("USER:"):
            return value[len("USER:"):]
        raise ValueError(value)

    monkeypatch.setattr(encryption, "protect_secret", protect_user)
    monkeypatch.setattr(encryption, "protect_secret_machine", protect_machine)
    monkeypatch.setattr(encryption, "unprotect_secret", unprotect)

    key = b"K" * 32
    service_path = tmp_path / "service.dpapi"
    user_path = tmp_path / "user.dpapi"

    DatabaseKeyStore(service_path, machine_scope=True).provision(key)
    DatabaseKeyStore(user_path).provision(key)

    assert calls[0][0] == "machine"
    assert calls[1][0] == "user"
    assert DatabaseKeyStore(service_path, machine_scope=True).load() == key
    assert DatabaseKeyStore(user_path).load() == key
    assert base64.b64encode(key).decode("ascii") not in service_path.read_text(encoding="utf-8").split("MACHINE:")[0]
