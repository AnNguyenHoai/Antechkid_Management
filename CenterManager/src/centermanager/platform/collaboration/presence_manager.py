# -*- coding: utf-8 -*-
"""PresenceManager - Track online sessions and collaboration state."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .heartbeat import HeartbeatRepository
from .runtime_lock import RuntimeLock
from .write_queue import WriteQueue, WriteRequest
from .runtime_session import RuntimeSession

logger = logging.getLogger(__name__)


class PresenceManager:
    """
    Tracks online sessions, current writer, lock owner, and queue state.
    Read-only service for collaboration status.
    """
    
    def __init__(
        self,
        heartbeat_repo: HeartbeatRepository,
        runtime_lock: RuntimeLock,
        write_queue: WriteQueue,
        timeout_seconds: int = 30,
    ):
        self._heartbeat_repo = heartbeat_repo
        self._runtime_lock = runtime_lock
        self._write_queue = write_queue
        self._timeout = timeout_seconds
    
    def get_online_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions with active heartbeat."""
        all_heartbeats = self._heartbeat_repo.get_all()
        online = []
        now = datetime.now()
        for session_id, data in all_heartbeats.items():
            last_seen = datetime.fromisoformat(data["last_seen"])
            if (now - last_seen).total_seconds() < self._timeout:
                online.append(data)
        return online
    
    def get_offline_sessions(self) -> List[Dict[str, Any]]:
        """Get sessions with expired heartbeat."""
        all_heartbeats = self._heartbeat_repo.get_all()
        offline = []
        now = datetime.now()
        for session_id, data in all_heartbeats.items():
            last_seen = datetime.fromisoformat(data["last_seen"])
            if (now - last_seen).total_seconds() >= self._timeout:
                offline.append(data)
        return offline
    
    def get_current_writer(self) -> Optional[Dict[str, Any]]:
        """Get the current lock owner information."""
        lock_info = self._runtime_lock.get_lock_info()
        if not lock_info.get("locked", False):
            return None
        return {
            "session_id": lock_info.get("session_id"),
            "username": lock_info.get("username"),
            "machine": lock_info.get("machine_fingerprint"),
            "acquired_at": lock_info.get("acquired_at"),
            "last_heartbeat": lock_info.get("last_heartbeat"),
        }
    
    def get_queue(self) -> List[Dict[str, Any]]:
        """Get all pending write requests."""
        requests = self._write_queue.get_requests()
        return [r.to_dict() for r in requests]
    
    def get_queue_length(self) -> int:
        """Get number of pending requests."""
        return self._write_queue.count()
    
    def get_next_writer(self) -> Optional[Dict[str, Any]]:
        """Get the next writer in queue."""
        request = self._write_queue.peek()
        if not request:
            return None
        return request.to_dict()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get full presence summary."""
        online = self.get_online_sessions()
        offline = self.get_offline_sessions()
        writer = self.get_current_writer()
        queue = self.get_queue()
        
        return {
            "online_count": len(online),
            "offline_count": len(offline),
            "online_sessions": online,
            "offline_sessions": offline,
            "current_writer": writer,
            "queue_length": len(queue),
            "queue": queue,
            "next_writer": self.get_next_writer(),
        }