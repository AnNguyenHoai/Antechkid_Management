"""EP-ARCH-04.7 — repository dependency direction and session lifecycle gate.

Source-driven architecture contract for the repository layer:
- repositories must not depend upward on application services/controllers/UI;
- repositories must not create SQLAlchemy engines or session factories/sessions;
- concrete repositories must keep receiving the application-owned Session via DI;
- repository modules must not own transaction/session lifecycle.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"

FORBIDDEN_UPWARD_MODULE_PREFIXES = (
    "centermanager.services", "centermanager.controllers", "centermanager.ui",
    "centermanager.views", "centermanager.application",
)
FORBIDDEN_SQLALCHEMY_IMPORTS = {
    "create_engine", "create_async_engine", "sessionmaker", "async_sessionmaker",
    "scoped_session", "async_scoped_session", "SessionLocal",
}
FORBIDDEN_LIFECYCLE_CALLS = {
    "create_engine", "create_async_engine", "sessionmaker", "async_sessionmaker",
    "scoped_session", "async_scoped_session", "Session", "AsyncSession",
    "begin", "begin_nested", "commit", "rollback",
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _repository_files() -> list[Path]:
    return sorted(REPOSITORIES.glob("*_repository.py"))


def _concrete_repository_files() -> list[Path]:
    return [p for p in _repository_files() if p.name not in {"provider.py"}]


def _imported_module_names(tree: ast.AST) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _attribute_calls(tree: ast.AST) -> list[tuple[int, str, str]]:
    calls: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            calls.append((node.lineno, "", func.id))
        elif isinstance(func, ast.Attribute):
            calls.append((node.lineno, func.attr, ast.unparse(func.value)))
    return calls


def test_ep_arch_04_7_repositories_do_not_depend_upward_on_application_layers():
    violations: list[str] = []
    for path in _repository_files():
        for lineno, module in _imported_module_names(_parse(path)):
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_UPWARD_MODULE_PREFIXES):
                violations.append(f"{path.name}:{lineno}: imports upward from {module}")
    assert not violations, "Repository modules must not depend upward on application/presentation layers:\n" + "\n".join(violations)


def test_ep_arch_04_7_repositories_do_not_import_sqlalchemy_session_factories():
    violations: list[str] = []
    for path in _repository_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sqlalchemy"):
                for alias in node.names:
                    if alias.name in FORBIDDEN_SQLALCHEMY_IMPORTS:
                        violations.append(f"{path.name}:{node.lineno}: imports sqlalchemy.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sqlalchemy.orm.session":
                        violations.append(f"{path.name}:{node.lineno}: imports sqlalchemy.orm.session")
    assert not violations, "Repositories must not create or own SQLAlchemy session factories/lifecycle:\n" + "\n".join(violations)


def test_ep_arch_04_7_repositories_do_not_instantiate_session_or_engine_lifecycle():
    violations: list[str] = []
    for path in _concrete_repository_files():
        for lineno, attr, receiver in _attribute_calls(_parse(path)):
            if attr in FORBIDDEN_LIFECYCLE_CALLS:
                violations.append(f"{path.name}:{lineno}: {receiver + '.' if receiver else ''}{attr}()")
    assert not violations, "Repositories must not instantiate Session/engine factories or control transaction lifecycle:\n" + "\n".join(violations)


def test_ep_arch_04_7_repository_constructors_receive_injected_session_and_store_it_privately():
    violations: list[str] = []
    for path in _concrete_repository_files():
        tree = _parse(path)
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("Repository") and n.name != "BaseRepository"]:
            init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
            if init is None:
                violations.append(f"{path.name}:{cls.name}: missing __init__")
                continue
            if not any(arg.arg == "session" for arg in init.args.args):
                violations.append(f"{path.name}:{cls.name}: __init__ must accept session explicitly")
                continue
            stores_session = any(
                isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self" and t.attr == "_session" for t in n.targets)
                and isinstance(n.value, ast.Name) and n.value.id == "session"
                for n in ast.walk(init)
            )
            delegates_to_base = any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Call)
                and isinstance(n.func.value.func, ast.Name)
                and n.func.value.func.id == "super"
                and n.func.attr == "__init__"
                for n in ast.walk(init)
            )
            if not stores_session and not delegates_to_base:
                violations.append(f"{path.name}:{cls.name}: injected session must be stored as self._session or delegated to BaseRepository")
    assert not violations, "Repository session dependency/lifecycle contract drift detected:\n" + "\n".join(violations)


def test_ep_arch_04_7_repositories_do_not_expose_session_factory_or_transaction_ownership_apis():
    forbidden_public = {"session", "commit", "rollback", "begin"}
    violations: list[str] = []
    for path in _repository_files():
        tree = _parse(path)
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("Repository")]:
            for node in cls.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden_public:
                    violations.append(f"{path.name}:{node.lineno}: public {node.name}()")
                if isinstance(node, ast.FunctionDef) and node.name == "session":
                    if any(isinstance(d, ast.Name) and d.id == "property" for d in node.decorator_list):
                        violations.append(f"{path.name}:{node.lineno}: public session property")
    assert not violations, "Repositories must not expose or own session/transaction lifecycle APIs:\n" + "\n".join(violations)
