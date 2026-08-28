# -*- coding: utf-8 -*-
"""Class domain mutation events emitted after successful database commits."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from centermanager.events.event import Event


@dataclass
class ClassCreated(Event):
    class_id: int
    class_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ClassUpdated(Event):
    class_id: int
    class_name: str
    changes: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ClassArchived(Event):
    class_id: int
    class_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ClassRestored(Event):
    class_id: int
    class_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ClassSessionChanged(Event):
    class_id: int
    session_id: int
    action: str
    timestamp: datetime = field(default_factory=datetime.now)
