# -*- coding: utf-8 -*-
"""Teacher domain mutation events.

Events are emitted only after the corresponding database mutation has committed
successfully. Timeline remains an audit/history concern and is intentionally
separate from this application event contract.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from centermanager.events.event import Event


@dataclass
class TeacherCreated(Event):
    teacher_id: int
    teacher_code: str
    teacher_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TeacherUpdated(Event):
    teacher_id: int
    teacher_code: str
    teacher_name: str
    changes: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TeacherArchived(Event):
    teacher_id: int
    teacher_code: str
    teacher_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TeacherRestored(Event):
    teacher_id: int
    teacher_code: str
    teacher_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TeacherAssignmentChanged(Event):
    teacher_id: int
    assignment_id: int
    class_id: int
    action: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TeacherDocumentChanged(Event):
    teacher_id: int
    document_id: int
    action: str
    timestamp: datetime = field(default_factory=datetime.now)
