"""Static service-to-service dependency audit for EP-ARCH-03.18.

The rule is intentionally narrow:
- application services may import other application services through the
  ``centermanager.services.<module>`` boundary;
- service imports must not create circular dependencies among service modules;
- service package wiring (``centermanager.services.__init__``) is excluded from
  the graph because it is the composition/export surface, not an application
  service implementation.

The test builds the import graph only from direct imports found in service
implementation modules and fails when a directed cycle exists.
"""
from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"


def _service_module_name(path: Path) -> str:
    return path.stem


def _service_dependency_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for source_path in sorted(SERVICES_DIR.glob("*_service.py")):
        module_name = _service_module_name(source_path)
        graph.setdefault(module_name, set())
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or not node.module:
                    continue
                imported_modules = [node.module]
            else:
                continue

            for imported in imported_modules:
                prefix = "centermanager.services."
                if not imported.startswith(prefix):
                    continue
                dependency = imported[len(prefix) :].split(".", 1)[0]
                if dependency.endswith("_service") and dependency != module_name:
                    graph[module_name].add(dependency)

    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            try:
                start = stack.index(node)
            except ValueError:
                return [node, node]
            return stack[start:] + [node]
        if node in visited:
            return None

        visiting.add(node)
        stack.append(node)
        for child in sorted(graph.get(node, ())):
            cycle = visit(child)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def test_service_dependency_graph_has_no_cycles() -> None:
    graph = _service_dependency_graph()
    cycle = _find_cycle(graph)
    assert cycle is None, f"Service dependency cycle detected: {' -> '.join(cycle or [])}"


def test_service_dependency_graph_contains_only_known_service_modules() -> None:
    graph = _service_dependency_graph()
    known = {path.stem for path in SERVICES_DIR.glob("*_service.py")}
    dangling = sorted(
        f"{source} -> {dependency}"
        for source, dependencies in graph.items()
        for dependency in dependencies
        if dependency not in known
    )
    assert not dangling, f"Dangling service dependencies detected: {dangling}"


def test_service_dependency_graph_is_stable_and_deterministic() -> None:
    graph = _service_dependency_graph()
    assert graph == _service_dependency_graph()
