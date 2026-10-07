from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.database import migration


def test_frozen_build_prefers_bundled_migrations_over_stale_external_copy(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "release"
    external = project_root / "migrations"
    external.mkdir(parents=True)

    bundled_root = tmp_path / "_MEI"
    bundled = bundled_root / "migrations"
    bundled.mkdir(parents=True)

    monkeypatch.setattr(
        migration,
        "_bundled_root",
        lambda: bundled_root,
    )

    assert migration._migration_root(project_root) == bundled


def test_frozen_build_prefers_bundled_alembic_ini_over_external_copy(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "release"
    project_root.mkdir(parents=True)
    external_ini = project_root / "alembic.ini"
    external_ini.write_text("[alembic]\n", encoding="utf-8")

    bundled_root = tmp_path / "_MEI"
    bundled_root.mkdir(parents=True)
    bundled_ini = bundled_root / "alembic.ini"
    bundled_ini.write_text("[alembic]\n", encoding="utf-8")

    monkeypatch.setattr(
        migration,
        "_bundled_root",
        lambda: bundled_root,
    )

    assert migration._alembic_ini_path(project_root) == bundled_ini


@pytest.mark.parametrize("missing", ["migrations", "alembic.ini"])
def test_frozen_build_fails_closed_when_bundled_schema_assets_are_missing(
    monkeypatch, tmp_path, missing
):
    project_root = tmp_path / "release"
    project_root.mkdir(parents=True)
    (project_root / "migrations").mkdir()
    (project_root / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    bundled_root = tmp_path / "_MEI"
    bundled_root.mkdir(parents=True)
    if missing != "migrations":
        (bundled_root / "migrations").mkdir()
    if missing != "alembic.ini":
        (bundled_root / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    monkeypatch.setattr(migration, "_bundled_root", lambda: bundled_root)

    with pytest.raises(RuntimeError, match="missing bundled"):
        if missing == "migrations":
            migration._migration_root(project_root)
        else:
            migration._alembic_ini_path(project_root)


def test_source_execution_keeps_using_checkout_migration_assets(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "checkout"
    migrations = project_root / "migrations"
    migrations.mkdir(parents=True)
    ini = project_root / "alembic.ini"
    ini.write_text("[alembic]\n", encoding="utf-8")

    monkeypatch.setattr(migration, "_bundled_root", lambda: None)

    assert migration._migration_root(project_root) == migrations
    assert migration._alembic_ini_path(project_root) == ini
