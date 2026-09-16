"""EP-ARCH-04.2 — RepositoryProvider completeness and consumer contract gate."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = ROOT / "src" / "centermanager" / "repositories"
SERVICES = ROOT / "src" / "centermanager" / "services"
PROVIDER = REPOSITORIES / "provider.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _repository_classes() -> dict[str, tuple[Path, str]]:
    result: dict[str, tuple[Path, str]] = {}
    for path in sorted(REPOSITORIES.glob("*_repository.py")):
        if path.name in {"base_repository.py", "provider.py"}:
            continue
        tree = _parse(path)
        classes = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name.endswith("Repository")
            and node.name != "BaseRepository"
        ]
        assert classes, f"{path.name}: no concrete *Repository class found"
        assert len(classes) == 1, f"{path.name}: expected one concrete repository, found {classes}"
        result[path.stem] = (path, classes[0])
    return result


def _provider_symbols() -> tuple[set[str], dict[str, ast.FunctionDef], dict[str, ast.FunctionDef]]:
    tree = _parse(PROVIDER)
    imported_classes: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("centermanager.repositories."):
            imported_classes.update(alias.name for alias in node.names)

    protocol = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RepositoryProvider"
    )
    implementation = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SqlAlchemyRepositoryProvider"
    )
    protocol_methods = {
        node.name: node
        for node in protocol.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    implementation_methods = {
        node.name: node
        for node in implementation.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return imported_classes, protocol_methods, implementation_methods


def _repository_return_name(node: ast.FunctionDef) -> str | None:
    annotation = node.returns
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def test_ep_arch_04_2_every_repository_is_registered_in_provider():
    imported_classes, _, _ = _provider_symbols()
    missing = [
        f"{path.name}: {class_name}"
        for _, (path, class_name) in _repository_classes().items()
        if class_name not in imported_classes
    ]
    assert not missing, "Concrete repositories missing from RepositoryProvider imports: " + ", ".join(missing)


def test_ep_arch_04_2_protocol_and_sqlalchemy_provider_have_identical_factory_surface():
    _, protocol_methods, implementation_methods = _provider_symbols()
    protocol_names = set(protocol_methods)
    implementation_names = set(implementation_methods)
    assert protocol_names == implementation_names, (
        "RepositoryProvider / SqlAlchemyRepositoryProvider factory drift: "
        f"protocol_only={sorted(protocol_names - implementation_names)}, "
        f"implementation_only={sorted(implementation_names - protocol_names)}"
    )


def test_ep_arch_04_2_provider_factories_return_and_construct_the_declared_repository():
    imported_classes, protocol_methods, implementation_methods = _provider_symbols()
    repository_class_names = set(imported_classes)
    for method_name, protocol_method in protocol_methods.items():
        return_name = _repository_return_name(protocol_method)
        assert return_name in repository_class_names, (
            f"{method_name}: protocol return type {return_name!r} is not a registered repository"
        )

        implementation = implementation_methods[method_name]
        assert isinstance(implementation, ast.FunctionDef)
        constructions = [
            node
            for node in ast.walk(implementation)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == return_name
        ]
        assert constructions, (
            f"{method_name}: SqlAlchemyRepositoryProvider does not construct {return_name}"
        )


def test_ep_arch_04_2_services_only_consume_declared_provider_factories():
    _, protocol_methods, _ = _provider_symbols()
    declared = set(protocol_methods)
    violations: list[str] = []

    for path in sorted(SERVICES.glob("*_service.py")):
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            if (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "self"
                and value.attr == "_repository_provider"
            ):
                if node.attr not in declared:
                    violations.append(f"{path.name}:{node.lineno}: _repository_provider.{node.attr}()")

    assert not violations, (
        "Services call RepositoryProvider factories that are absent from the protocol: "
        + ", ".join(violations)
    )
