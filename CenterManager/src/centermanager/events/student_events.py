# -*- coding: utf-8 -*-
"""Student domain events."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from centermanager.events.event import Event


@dataclass
class StudentArchived(Event):
    """Event emitted when a student is archived."""
    student_id: int
    student_code: str
    student_name: str
    previous_status: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StudentActivated(Event):
    """Event emitted when a student is activated (restored from archive)."""
    student_id: int
    student_code: str
    student_name: str
    previous_status: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StudentDeleted(Event):
    """Event emitted when a student is soft-deleted."""
    student_id: int
    student_code: str
    student_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StudentUpdated(Event):
    """Event emitted when a student is updated."""
    student_id: int
    student_code: str
    student_name: str
    changes: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class StudentEnrollmentChanged(Event):
    """Event emitted after an enrollment lifecycle mutation is committed."""
    student_id: int
    enrollment_id: int
    class_id: int
    action: str
    previous_status: Optional[str]
    current_status: str
    timestamp: datetime = field(default_factory=datetime.now)
