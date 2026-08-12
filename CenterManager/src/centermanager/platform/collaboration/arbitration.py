# -*- coding: utf-8 -*-
"""Arbitration - Write arbitration rules and priority."""

from enum import IntEnum
from typing import List
from datetime import datetime

from .write_queue import WriteRequest


class Priority(IntEnum):
    """Priority levels for write requests."""
    ADMIN = 100
    MANAGER = 80
    TEACHER = 60
    RECEPTION = 40
    USER = 20
    
    @classmethod
    def from_role(cls, role: str) -> int:
        """Get priority from role name."""
        role_map = {
            "admin": cls.ADMIN,
            "manager": cls.MANAGER,
            "teacher": cls.TEACHER,
            "reception": cls.RECEPTION,
        }
        return role_map.get(role.lower(), cls.USER)


class Arbitration:
    """Write arbitration rules."""
    
    @staticmethod
    def sort_requests(requests: List[WriteRequest]) -> List[WriteRequest]:
        """Sort requests by priority DESC, then timestamp ASC."""
        return sorted(requests, key=lambda r: (-r.priority, r.timestamp))
    
    @staticmethod
    def get_next_request(requests: List[WriteRequest]) -> WriteRequest:
        """Get the next request based on arbitration rules."""
        if not requests:
            raise ValueError("No requests to process")
        sorted_reqs = Arbitration.sort_requests(requests)
        return sorted_reqs[0]
    
    @staticmethod
    def is_higher_priority(req1: WriteRequest, req2: WriteRequest) -> bool:
        """Check if req1 has higher priority than req2."""
        if req1.priority != req2.priority:
            return req1.priority > req2.priority
        return req1.timestamp < req2.timestamp