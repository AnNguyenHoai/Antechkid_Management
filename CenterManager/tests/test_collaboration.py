import pytest
import json
from pathlib import Path

from centermanager.platform.collaboration import (
    CollaborationManager,
    ModeManager,
    LockManager,
    EditSessionManager,
    CollaborationMode,
)
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.platform.collaboration.metadata_repository import MetadataRepository
from centermanager.platform.collaboration.lock_repository import LockRepository
from centermanager.events.event_bus import EventBus
from centermanager.core.current_user import set_current_user
from centermanager.models.user import User


@pytest.fixture
def temp_metadata(tmp_path):
    return tmp_path / "metadata"


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def metadata_repository(temp_metadata):
    return JsonMetadataRepository(temp_metadata)


@pytest.fixture
def lock_repository(temp_metadata):
    lock_file = temp_metadata / "lock.json"
    return JsonLockRepository(lock_file)


@pytest.fixture
def collaboration_manager(temp_metadata, event_bus):
    user = User(username="test_user", full_name="Test User")
    set_current_user(user)
    return CollaborationManager(temp_metadata, event_bus)


def test_mode_manager():
    mm = ModeManager()
    assert mm.current_mode() == CollaborationMode.READ
    mm.set_mode(CollaborationMode.WRITE)
    assert mm.current_mode() == CollaborationMode.WRITE


def test_lock_manager(lock_repository):
    lm = LockManager(lock_repository)
    assert not lm.is_locked()
    assert lm.acquire("user1", "sess1") is True
    assert lm.is_locked()
    assert lm.get_owner() == "user1"
    assert lm.acquire("user2", "sess2") is False
    assert lm.release("user2") is False
    assert lm.release("user1") is True
    assert not lm.is_locked()


def test_edit_session_manager():
    esm = EditSessionManager()
    assert not esm.is_active()
    sid = esm.start_session("user1")
    assert esm.is_active()
    assert esm.get_owner() == "user1"
    assert esm.get_session_id() == sid
    esm.end_session()
    assert not esm.is_active()


def test_collaboration_manager_request_write(collaboration_manager):
    cm = collaboration_manager
    assert cm.current_mode() == CollaborationMode.READ
    assert cm.request_write() is True
    assert cm.current_mode() == CollaborationMode.WRITE
    assert cm.get_session_info()['active'] is True


def test_collaboration_manager_release_write(collaboration_manager):
    cm = collaboration_manager
    cm.request_write()
    assert cm.current_mode() == CollaborationMode.WRITE
    assert cm.release_write() is True
    assert cm.current_mode() == CollaborationMode.READ
    assert not cm.get_session_info()['active']


def test_collaboration_manager_metadata_creation(temp_metadata, event_bus):
    cm = CollaborationManager(temp_metadata, event_bus)
    assert (temp_metadata / "lock.json").exists()
    assert (temp_metadata / "version.json").exists()
    assert (temp_metadata / "deployment.json").exists()
    with open(temp_metadata / "lock.json") as f:
        data = json.load(f)
        assert data["locked"] is False
        assert data["owner"] is None
    with open(temp_metadata / "version.json") as f:
        data = json.load(f)
        assert data["platform_version"] == 1
    with open(temp_metadata / "deployment.json") as f:
        data = json.load(f)
        assert data["profile"] == "Standalone"


def test_collaboration_manager_get_version(collaboration_manager):
    assert collaboration_manager.get_version() == 1


def test_collaboration_manager_get_deployment_profile(collaboration_manager):
    assert collaboration_manager.get_deployment_profile() == "Standalone"


def test_collaboration_manager_ensure_write(collaboration_manager):
    cm = collaboration_manager
    assert cm.ensure_write() is False
    cm.request_write()
    assert cm.ensure_write() is True


def test_metadata_repository(temp_metadata):
    from centermanager.platform.collaboration import JsonMetadataRepository
    repo = JsonMetadataRepository(temp_metadata)
    # Lock
    lock_data = repo.load_lock()
    assert lock_data == {}
    repo.save_lock({"locked": True})
    loaded = repo.load_lock()
    assert loaded["locked"] is True

    # Version
    version_data = repo.load_version()
    assert version_data == {}
    repo.save_version({"platform_version": 42})
    loaded = repo.load_version()
    assert loaded["platform_version"] == 42

    # Deployment
    deployment_data = repo.load_deployment()
    assert deployment_data == {}
    repo.save_deployment({"profile": "Test"})
    loaded = repo.load_deployment()
    assert loaded["profile"] == "Test"


def test_lock_repository(temp_metadata):
    from centermanager.platform.collaboration import JsonLockRepository
    lock_file = temp_metadata / "lock.json"
    repo = JsonLockRepository(lock_file)
    lock = repo.get_lock()
    assert lock["locked"] is False
    repo.save_lock({"locked": True, "owner": "test"})
    loaded = repo.get_lock()
    assert loaded["locked"] is True
    assert loaded["owner"] == "test"