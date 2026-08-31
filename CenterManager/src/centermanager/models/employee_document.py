from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from centermanager.database.base import Base

class EmployeeDocument(Base):
    __tablename__='employee_documents'
    TYPE_CV='CV'; TYPE_OTHER='OTHER'
    id: Mapped[int]=mapped_column(primary_key=True)
    employee_id: Mapped[int]=mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    document_type: Mapped[str]=mapped_column(String(30), nullable=False, default=TYPE_OTHER)
    original_filename: Mapped[str]=mapped_column(String(255), nullable=False)
    relative_path: Mapped[str]=mapped_column(String(500), nullable=False)
    notes: Mapped[Optional[str]]=mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime]=mapped_column(DateTime, nullable=False, default=datetime.utcnow)
