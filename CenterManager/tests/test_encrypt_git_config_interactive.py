# -*- coding: utf-8 -*-
"""Regression coverage for the interactive Git bundle helper."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "encrypt_git_config.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("encrypt_git_config_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_encrypt_git_config_cli_fields_are_optional_for_interactive_mode(monkeypatch):
    module = _load_script_module()
    monkeypatch.setattr("sys.argv", [str(SCRIPT)])
    args = module._build_parser().parse_args()

    assert args.repository is None
    assert args.username is None
    assert args.token is None
    assert args.branch is None
    assert args.email is None


def test_prompt_optional_uses_main_branch_default(monkeypatch):
    module = _load_script_module()
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert module._prompt_optional("Git branch", None, default="main") == "main"
