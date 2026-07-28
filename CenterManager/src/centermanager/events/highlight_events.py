# -*- coding: utf-8 -*-
"""
Domain events for Student Highlight.
"""
from dataclasses import dataclass

from centermanager.events.event import Event


@dataclass
class StudentHighlightCreated(Event):
    highlight_id: int
    student_id: int
    session_id: int
    title: str
    highlight_type: str
    description: str = None