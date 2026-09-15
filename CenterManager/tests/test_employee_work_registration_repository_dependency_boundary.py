"""Regression contract for EmployeeWorkRegistration repository composition."""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = PROJECT_ROOT / "src" / "centermanager" / "services" / "employee_work_registration_service.py"


def test_ewr_service_depends_on_provider_contract_not_concrete_provider():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SERVICE_PATH))

    repository_imports = []
    concrete_provider_constructors = []
    audit_service_provider_injection = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("centermanager.repositories"):
            if node.module != "centermanager.repositories.provider":
                repository_imports.append(node.module)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "SqlAlchemyRepositoryProvider":
                concrete_provider_constructors.append(node.func.id)
            if isinstance(node.func, ast.Name) and node.func.id == "AuditService":
                for kw in node.keywords:
                    if kw.arg == "repository_provider" and isinstance(kw.value, ast.Attribute):
                        if kw.value.attr == "_repository_provider":
                            audit_service_provider_injection = True

    assert not repository_imports
    assert not concrete_provider_constructors
    assert audit_service_provider_injection


def test_ewr_service_uses_default_provider_factory_at_boundary():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider" in source
    assert "self._repository_provider=repository_provider or create_default_repository_provider()" in source
