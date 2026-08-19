import pytest
import json
from pathlib import Path

from centermanager.platform.collaboration import (
    CollaborationManager,
    CollaborationMode,
    ModeManager,
    LockManager,
    EditSessionManager,
)
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.events.event_bus import EventBus
from centermanager.core.current_user import set_current_user
from centermanager.models.user import User


@pytest.fixture
def temp_metadata(tmp_path):
    """Create temporary metadata directory."""
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    return metadata_dir


@pytest.fixture
def lock_repository(temp_metadata):
    """Create lock repository."""
    lock_file = temp_metadata / "lock.json"
    return JsonLockRepository(lock_file)


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def collaboration_manager(temp_metadata, event_bus):
    """Create collaboration manager with initialization."""
    user = User(username="test_user", full_name="Test User")
    set_current_user(user)
    cm = CollaborationManager(runtime_root=temp_metadata.parent, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    return cm


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
    assert cm.current_mode() == "READ"
    result = cm.request_write()
    assert result.is_granted is True
    assert cm.current_mode() == "WRITE"
    # get_session_info không tồn tại, dùng get_session
    session = cm.get_session()
    assert session is not None


def test_collaboration_manager_release_write(collaboration_manager):
    cm = collaboration_manager
    cm.request_write()
    assert cm.current_mode() == "WRITE"
    assert cm.release_write() is True
    assert cm.current_mode() == "READ"


def test_collaboration_manager_metadata_creation(temp_metadata, event_bus):
    """Test that collaboration directory is created and lock.json exists after acquire."""
    cm = CollaborationManager(runtime_root=temp_metadata.parent, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")
    
    # Collaboration directory should exist
    collab_dir = temp_metadata.parent / "collaboration"
    assert collab_dir.exists()
    
    # lock.json should not exist yet (no lock acquired)
    assert not (collab_dir / "lock.json").exists()
    
    # Acquire lock to create lock.json
    cm.request_write()
    assert (collab_dir / "lock.json").exists()
    
    # Verify lock.json content
    with open(collab_dir / "lock.json") as f:
        data = json.load(f)
        assert data["locked"] is True
        assert data["session_id"] is not None


def test_collaboration_manager_get_version(collaboration_manager):
    # Version trả về lock_timeout (placeholder), chỉ cần > 0
    assert collaboration_manager.get_version() > 0


def test_collaboration_manager_get_deployment_profile(collaboration_manager):
    assert collaboration_manager.get_deployment_profile() == "Standalone"


def test_collaboration_manager_ensure_write(collaboration_manager):
    cm = collaboration_manager
    assert cm.ensure_write() is False
    cm.request_write()
    assert cm.ensure_write() is True


def test_metadata_repository(temp_metadata):
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
    lock_file = temp_metadata / "lock.json"
    repo = JsonLockRepository(lock_file)
    lock = repo.get_lock()
    assert lock["locked"] is False
    repo.save_lock({"locked": True, "owner": "test"})
    loaded = repo.get_lock()
    assert loaded["locked"] is True
    assert loaded["owner"] == "test"