# -*- coding: utf-8 -*-
"""Tests for Repository Foundation."""

import pytest
import json
from pathlib import Path

from centermanager.platform.repository import (
    RepositoryState,
    RepositoryManager,
    ManifestLoader,
    RuntimeValidator,
    AtomicFileWriter,
    RepositoryNotFoundError,
    ManifestInvalidError,
    ManifestNotFoundError,
    RuntimeValidationFailedError,
)


class TestRepositoryState:
    def test_values(self):
        assert RepositoryState.NOT_FOUND.value == "not_found"
        assert RepositoryState.READY.value == "ready"
        assert RepositoryState.INVALID.value == "invalid"
        assert RepositoryState.CORRUPTED.value == "corrupted"
        assert RepositoryState.OFFLINE.value == "offline"

    def test_is_operational(self):
        assert RepositoryState.READY.is_operational()
        assert not RepositoryState.NOT_FOUND.is_operational()
        assert not RepositoryState.INVALID.is_operational()

    def test_needs_recovery(self):
        assert RepositoryState.INVALID.needs_recovery()
        assert RepositoryState.CORRUPTED.needs_recovery()
        assert not RepositoryState.READY.needs_recovery()
        assert not RepositoryState.NOT_FOUND.needs_recovery()


class TestManifestLoader:
    def test_load_missing(self, tmp_path):
        loader = ManifestLoader(tmp_path / "manifest.json")
        assert not loader.exists()
        with pytest.raises(ManifestNotFoundError):
            loader.load()

    def test_load_valid(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        data = {
            "schema_version": 1,
            "runtime_version": 42,
            "database_version": 5,
            "minimum_app_version": "1.0.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": "2026-08-10T10:00:00",
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loader = ManifestLoader(manifest_path)
        assert loader.exists()
        loaded = loader.load()
        assert loaded["runtime_version"] == 42
        assert loaded["schema_version"] == 1

    def test_load_invalid_json(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        loader = ManifestLoader(manifest_path)
        with pytest.raises(ManifestInvalidError):
            loader.load()

    def test_load_missing_fields(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        data = {"schema_version": 1}  # missing required fields
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loader = ManifestLoader(manifest_path)
        with pytest.raises(ManifestInvalidError) as exc:
            loader.load()
        assert "runtime_version" in str(exc.value)

    def test_exists(self, tmp_path):
        loader = ManifestLoader(tmp_path / "manifest.json")
        assert not loader.exists()
        manifest_path = tmp_path / "manifest.json"
        manifest_path.touch()
        assert loader.exists()


class TestRuntimeValidator:
    def test_validate_ready(self, tmp_path):
        validator = RuntimeValidator(tmp_path)
        # Create required directories
        for d in ["database", "metadata", "reports", "attachments", "collaboration"]:
            (tmp_path / d).mkdir(parents=True)

        assert validator.validate() is True

    def test_validate_missing_dir(self, tmp_path):
        validator = RuntimeValidator(tmp_path)
        # Create only some directories
        (tmp_path / "database").mkdir(parents=True)

        assert validator.validate() is False
        missing = validator.get_missing_dirs()
        assert "metadata" in missing
        assert "reports" in missing
        assert "attachments" in missing
        assert "collaboration" in missing

    def test_validate_no_exception(self, tmp_path):
        validator = RuntimeValidator(tmp_path)
        # Should not raise by default
        assert validator.validate() is False

        # With raise_on_error
        with pytest.raises(RuntimeValidationFailedError):
            validator.validate(raise_on_error=True)


class TestAtomicFileWriter:
    def test_write_string(self, tmp_path):
        file_path = tmp_path / "test.txt"
        writer = AtomicFileWriter(file_path)
        writer.write("hello world")

        assert file_path.exists()
        with open(file_path, "r", encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_write_json(self, tmp_path):
        file_path = tmp_path / "test.json"
        writer = AtomicFileWriter(file_path)
        data = {"key": "value", "number": 42}
        writer.write_json(data)

        assert file_path.exists()
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["key"] == "value"
        assert loaded["number"] == 42

    def test_write_with_serializer(self, tmp_path):
        file_path = tmp_path / "test.txt"
        writer = AtomicFileWriter(file_path)
        writer.write({"a": 1}, lambda d: f"data: {d['a']}")

        with open(file_path, "r", encoding="utf-8") as f:
            assert f.read() == "data: 1"

    def test_atomic_property(self, tmp_path):
        file_path = tmp_path / "test.txt"
        writer = AtomicFileWriter(file_path)

        # Write first
        writer.write("first")
        assert file_path.exists()
        with open(file_path, "r", encoding="utf-8") as f:
            assert f.read() == "first"

        # Write second - should replace atomically
        writer.write("second")
        with open(file_path, "r", encoding="utf-8") as f:
            assert f.read() == "second"


class TestRepositoryManager:
    def test_detect_not_found(self, tmp_path):
        """Repository root does not exist -> NOT_FOUND."""
        non_existent = tmp_path / "does_not_exist"
        manager = RepositoryManager(runtime_root=non_existent)
        state = manager.detect()
        assert state == RepositoryState.NOT_FOUND

    def test_detect_invalid(self, tmp_path):
        """Root exists but no manifest -> INVALID."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        manager = RepositoryManager(runtime_root=tmp_path)
        state = manager.detect()
        assert state == RepositoryState.INVALID

    def test_detect_corrupted(self, tmp_path):
        """Manifest exists but invalid -> CORRUPTED."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        manifest_path = tmp_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{invalid}")

        manager = RepositoryManager(runtime_root=tmp_path)
        state = manager.detect()
        assert state == RepositoryState.CORRUPTED

    def test_detect_ready(self, tmp_path):
        """All required files and directories exist -> READY."""
        tmp_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest_path = tmp_path / "manifest.json"
        data = {
            "schema_version": 1,
            "runtime_version": 1,
            "database_version": 1,
            "minimum_app_version": "0.1.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": "2026-08-10T10:00:00",
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Create required directories
        for d in ["database", "metadata", "reports", "attachments", "collaboration"]:
            (tmp_path / d).mkdir(parents=True)

        manager = RepositoryManager(runtime_root=tmp_path)
        state = manager.detect()
        assert state == RepositoryState.READY

    def test_validate(self, tmp_path):
        manager = RepositoryManager(runtime_root=tmp_path)
        assert manager.validate() is False

        # Make it ready
        tmp_path.mkdir(parents=True, exist_ok=True)
        manifest_path = tmp_path / "manifest.json"
        data = {
            "schema_version": 1,
            "runtime_version": 1,
            "database_version": 1,
            "minimum_app_version": "0.1.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": "2026-08-10T10:00:00",
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        for d in ["database", "metadata", "reports", "attachments", "collaboration"]:
            (tmp_path / d).mkdir(parents=True)

        # Refresh to clear cache
        manager.refresh()
        assert manager.validate() is True

    def test_manifest(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        manifest_path = tmp_path / "manifest.json"
        data = {
            "schema_version": 1,
            "runtime_version": 42,
            "database_version": 5,
            "minimum_app_version": "1.0.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": "2026-08-10T10:00:00",
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        manager = RepositoryManager(runtime_root=tmp_path)
        manifest = manager.manifest()
        assert manifest is not None
        assert manifest["runtime_version"] == 42

        # Missing manifest
        manager2 = RepositoryManager(runtime_root=tmp_path.parent / "missing")
        assert manager2.manifest() is None

    def test_state_cache(self, tmp_path):
        """Test that state is cached and refresh clears cache."""
        non_existent = tmp_path / "does_not_exist"
        manager = RepositoryManager(runtime_root=non_existent)

        # First call detects
        state1 = manager.state()
        assert state1 == RepositoryState.NOT_FOUND

        # Second call uses cache
        state2 = manager.state()
        assert state2 == RepositoryState.NOT_FOUND
        assert state1 is state2  # same cached object

        # Force refresh re-detects (still NOT_FOUND)
        state3 = manager.state(force_refresh=True)
        assert state3 == RepositoryState.NOT_FOUND

    def test_refresh(self, tmp_path):
        """Test that refresh clears cache and re-detects."""
        non_existent = tmp_path / "does_not_exist"
        manager = RepositoryManager(runtime_root=non_existent)

        # Initially NOT_FOUND
        assert manager.state() == RepositoryState.NOT_FOUND

        # Now create a valid repository at that path
        non_existent.mkdir(parents=True, exist_ok=True)
        manifest_path = non_existent / "manifest.json"
        data = {
            "schema_version": 1,
            "runtime_version": 1,
            "database_version": 1,
            "minimum_app_version": "0.1.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": "2026-08-10T10:00:00",
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        for d in ["database", "metadata", "reports", "attachments", "collaboration"]:
            (non_existent / d).mkdir(parents=True)

        # Without refresh, cache still says NOT_FOUND
        assert manager.state() == RepositoryState.NOT_FOUND

        # Refresh should re-detect and return READY
        manager.refresh()
        assert manager.state() == RepositoryState.READY