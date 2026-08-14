# -*- coding: utf-8 -*-
"""WriteQueue - Shared write queue with file-per-request storage."""

import json
import uuid
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from centermanager.platform.repository.atomic_file_writer import AtomicFileWriter
from .exceptions import QueueEmptyError
from .runtime_session import RuntimeSession

logger = logging.getLogger(__name__)


class WriteRequest:
    """A single write request."""
    
    def __init__(
        self,
        request_id: str,
        session_id: str,
        user_id: str,
        username: str,
        role: str,
        priority: int,
        timestamp: datetime,
        reason: str = "",
        status: str = "pending",
    ):
        self.request_id = request_id
        self.session_id = session_id
        self.user_id = user_id
        self.username = username
        self.role = role
        self.priority = priority
        self.timestamp = timestamp
        self.reason = reason
        self.status = status  # pending, granted, cancelled, expired
    
    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WriteRequest":
        return cls(
            request_id=data["request_id"],
            session_id=data["session_id"],
            user_id=data["user_id"],
            username=data["username"],
            role=data["role"],
            priority=data["priority"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data.get("reason", ""),
            status=data.get("status", "pending"),
        )


class WriteQueue:
    """
    Shared write queue stored as individual files in collaboration/queue/.
    Each request is one file.
    """
    
    def __init__(self, queue_dir: Path):
        self._queue_dir = queue_dir
        self._queue_dir.mkdir(parents=True, exist_ok=True)
    
    def enqueue(self, request: WriteRequest) -> None:
        """Add a request to the queue."""
        file_path = self._queue_dir / f"{request.request_id}.json"
        writer = AtomicFileWriter(file_path)
        writer.write_json(request.to_dict())
        logger.info(f"Enqueued write request {request.request_id} for {request.username}")
    
    def dequeue(self) -> Optional[WriteRequest]:
        """Remove and return the highest priority request."""
        requests = self._list_requests()
        if not requests:
            return None
        
        requests.sort(key=lambda r: (-r.priority, r.timestamp))
        request = requests[0]
        self._delete_request(request.request_id)
        return request
    
    def peek(self) -> Optional[WriteRequest]:
        """Get the highest priority request without removing."""
        requests = self._list_requests()
        if not requests:
            return None
        
        requests.sort(key=lambda r: (-r.priority, r.timestamp))
        return requests[0]
    
    def get_requests(self) -> List[WriteRequest]:
        """Get all pending requests."""
        return self._list_requests()
    
    def count(self) -> int:
        """Get number of pending requests."""
        return len(self._list_requests())
    
    def cancel(self, request_id: str) -> bool:
        """Cancel a pending request."""
        file_path = self._queue_dir / f"{request_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cancelled write request {request_id}")
            return True
        return False
    
    def has_pending(self, session_id: str) -> bool:
        """Check if a session has a pending request."""
        for req in self._list_requests():
            if req.session_id == session_id:
                return True
        return False
    
    def cancel_for_session(self, session_id: str) -> None:
        """Cancel all pending requests for a session."""
        for req in self._list_requests():
            if req.session_id == session_id:
                self.cancel(req.request_id)
    
    def clear(self) -> None:
        """Clear all pending requests."""
        for file in self._queue_dir.glob("*.json"):
            file.unlink()
        logger.info("Cleared all pending write requests")
    
    def _list_requests(self) -> List[WriteRequest]:
        """List all pending requests."""
        requests = []
        for file in self._queue_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") == "pending":
                    requests.append(WriteRequest.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to load request from {file}: {e}")
        return requests
    
    def _delete_request(self, request_id: str) -> None:
        """Delete a request file."""
        file_path = self._queue_dir / f"{request_id}.json"
        if file_path.exists():
            file_path.unlink()