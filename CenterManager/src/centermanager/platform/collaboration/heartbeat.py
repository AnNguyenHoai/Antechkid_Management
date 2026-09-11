# -*- coding: utf-8 -*-
"""Heartbeat - Periodic heartbeat management."""

import json
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from centermanager.platform.repository.atomic_file_writer import AtomicFileWriter
from .runtime_session import RuntimeSession

logger = logging.getLogger(__name__)


class HeartbeatRepository:
    """
    Stores heartbeat files in collaboration/heartbeat/.
    Each session has its own heartbeat file.
    """
    
    def __init__(self, heartbeat_dir: Path):
        self._heartbeat_dir = heartbeat_dir
        self._heartbeat_dir.mkdir(parents=True, exist_ok=True)
    
    def update(self, session: RuntimeSession) -> None:
        """Update heartbeat for a session."""
        session.update_heartbeat()
        file_path = self._heartbeat_dir / f"{session.session_id}.json"
        writer = AtomicFileWriter(file_path)
        writer.write_json({
            "session_id": session.session_id,
            "machine_fingerprint": session.machine_fingerprint,
            "user_id": session.user_id,
            "username": session.username,
            "last_seen": session.last_heartbeat.isoformat(),
            "runtime_version": session.runtime_version,
            "is_active": session.is_active,
        })
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all heartbeat entries."""
        result = {}
        for file in self._heartbeat_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result[data["session_id"]] = data
            except Exception as e:
                logger.warning(f"Failed to load heartbeat from {file}: {e}")
        return result
    
    def remove(self, session_id: str) -> None:
        """Remove heartbeat file for a session."""
        file_path = self._heartbeat_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Removed heartbeat for session {session_id}")
    
    def is_expired(self, session_id: str, timeout_seconds: int = 30) -> bool:
        """Check if a session's heartbeat has expired."""
        file_path = self._heartbeat_dir / f"{session_id}.json"
        if not file_path.exists():
            return True
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_seen = datetime.fromisoformat(data["last_seen"])
            return (datetime.now() - last_seen).total_seconds() > timeout_seconds
        except Exception:
            return True


class HeartbeatManager:
    """
    Manages heartbeat updates for the current session.
    Runs in a background thread.
    """
    
    def __init__(
        self,
        repo: HeartbeatRepository,
        session: RuntimeSession,
        interval_seconds: int = 10,
        callback: Optional[callable] = None,
    ):
        self._repo = repo
        self._session = session
        self._interval = interval_seconds
        self._callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the heartbeat thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started heartbeat for session {self._session.session_id}")
    
    def stop(self) -> None:
        """Stop the heartbeat thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._repo.remove(self._session.session_id)
        logger.info(f"Stopped heartbeat for session {self._session.session_id}")
    
    def update(self) -> None:
        """Update heartbeat immediately."""
        self._repo.update(self._session)
        if self._callback:
            self._callback(self._session)
    
    def _heartbeat_loop(self) -> None:
        """Background heartbeat loop."""
        while self._running:
            try:
                self.update()
                time.sleep(self._interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                time.sleep(self._interval)