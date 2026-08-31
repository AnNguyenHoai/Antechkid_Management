from __future__ import annotations
from pathlib import Path
import shutil, uuid
from sqlalchemy.orm import sessionmaker
from centermanager.models.employee_document import EmployeeDocument

class EmployeeDocumentService:
    def __init__(self, session_factory: sessionmaker, attachments_root: Path):
        self._sf=session_factory; self._root=Path(attachments_root)/'Employees'
    def list_documents(self, employee_id):
        with self._sf() as s:return s.query(EmployeeDocument).filter_by(employee_id=employee_id).order_by(EmployeeDocument.uploaded_at.desc()).all()
    def upload(self, employee, source_path, document_type='CV', notes=None):
        src=Path(source_path)
        if not src.exists(): raise FileNotFoundError(src)
        folder=self._root/employee.employee_code/document_type
        folder.mkdir(parents=True, exist_ok=True)
        name=f'{uuid.uuid4().hex}_{src.name}'
        dst=folder/name; shutil.copy2(src,dst)
        rel=str(dst.relative_to(self._root.parent.parent)) if self._root.parent.parent in dst.parents else str(dst)
        with self._sf() as s:
            d=EmployeeDocument(employee_id=employee.id,document_type=document_type,original_filename=src.name,relative_path=rel,notes=notes)
            s.add(d); s.commit(); s.refresh(d); return d
