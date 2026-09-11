from __future__ import annotations
from pathlib import Path
import shutil, uuid
import os
import hashlib
import logging
from sqlalchemy.orm import sessionmaker
from centermanager.models.employee_document import EmployeeDocument

logger = logging.getLogger(__name__)

class EmployeeDocumentService:
    def __init__(self, session_factory: sessionmaker, attachments_root: Path):
        self._sf = session_factory
        self._attachments_root = Path(attachments_root)
        self._root = self._attachments_root / 'Employees'
        self._runtime_root = self._attachments_root.parent

    def resolve_document_path(self, document: EmployeeDocument) -> Path:
        """Resolve a stored document path against the runtime root safely.

        Employee document metadata stores paths relative to the runtime directory,
        while QFile/os.startfile resolves relative paths against the process CWD.
        Always return an absolute, managed path and reject path traversal.
        """
        raw = Path(document.relative_path)
        if raw.is_absolute():
            candidate = raw.resolve()
        elif raw.parts and raw.parts[0].lower() == self._attachments_root.name.lower():
            candidate = (self._runtime_root / raw).resolve()
        else:
            # Legacy records may store Employees/... relative to Attachments.
            candidate = (self._attachments_root / raw).resolve()

        allowed = self._attachments_root.resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError as exc:
            raise ValueError("Employee document path is outside the managed attachments directory.") from exc
        return candidate

    def openable_path(self, document_id: int) -> Path:
        with self._sf() as s:
            document = s.get(EmployeeDocument, document_id)
            if document is None:
                raise FileNotFoundError(f"Employee document {document_id} not found.")
            path = self.resolve_document_path(document)
        if not path.is_file():
            raise FileNotFoundError(f"Employee document file not found: {path}")
        return path
    def list_documents(self, employee_id):
        with self._sf() as s:return s.query(EmployeeDocument).filter_by(employee_id=employee_id).order_by(EmployeeDocument.uploaded_at.desc()).all()
    def get_runtime_employee_root(self, employee_code: str) -> Path:
        """Return the canonical local storage root for an employee's documents."""
        return self._root / employee_code

    def get_repository_employee_root(self, employee_code: str) -> Path:
        """Return the canonical repository mirror root for an employee's documents."""
        # runtime_root is .../runtime; repository is .../runtime/repository
        return self._runtime_root / "repository" / "Attachments" / "Employees" / employee_code

    def get_repository_relative_path(self, document: EmployeeDocument) -> Path:
        """Return the path that publish will materialize inside the Git repository."""
        relative = Path(document.relative_path)
        if relative.is_absolute():
            raise ValueError("Employee document paths must be relative.")
        # Stored employee paths are relative to runtime, e.g.
        # Attachments/Employees/EMP-00001/CV/file.pdf.
        return relative

    def document_sync_locations(self, document: EmployeeDocument) -> dict:
        """Describe local and repository locations for diagnostics/UI."""
        runtime_path = self.resolve_document_path(document)
        repo_path = (self._runtime_root / "repository" / self.get_repository_relative_path(document)).resolve()
        repo_root = (self._runtime_root / "repository").resolve()
        try:
            repo_path.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError("Employee document repository path escapes the repository root.") from exc
        runtime_exists = runtime_path.is_file()
        repository_exists = repo_path.is_file()
        checksum_match = False
        if runtime_exists and repository_exists:
            try:
                checksum_match = self.file_sha256(runtime_path) == self.file_sha256(repo_path)
            except OSError:
                checksum_match = False

        return {
            "runtime_path": runtime_path,
            "repository_path": repo_path,
            "runtime_exists": runtime_exists,
            "repository_exists": repository_exists,
            # "synced" means the two physical copies exist and contain the
            # same bytes, not merely that both paths exist.
            "checksum_match": checksum_match,
            "synced": runtime_exists and repository_exists and checksum_match,
        }

    def file_sha256(self, path: Path) -> str:
        """Return a deterministic checksum for document sync diagnostics."""
        digest = hashlib.sha256()
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def verify_repository_sync(self, document: EmployeeDocument) -> dict:
        """Return a deterministic sync diagnostic for a document.

        A document is considered synchronized only when both the local runtime
        materialization and the repository copy exist and have identical SHA-256
        content. This makes cross-machine verification explicit.
        """
        result = self.document_sync_locations(document)
        logger.info(
            "Employee document sync check: document_id=%s runtime=%s repository=%s "
            "runtime_exists=%s repository_exists=%s checksum_match=%s synced=%s",
            getattr(document, "id", None),
            result["runtime_path"],
            result["repository_path"],
            result["runtime_exists"],
            result["repository_exists"],
            result["checksum_match"],
            result["synced"],
        )
        return result

    def upload(self, employee, source_path, document_type='CV', notes=None):
        src = Path(source_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(src)

        folder = self.get_runtime_employee_root(employee.employee_code) / document_type
        folder.mkdir(parents=True, exist_ok=True)

        name = f'{uuid.uuid4().hex}_{src.name}'
        dst = (folder / name).resolve()

        # The destination must stay inside managed Employee attachments.
        allowed = self._attachments_root.resolve()
        try:
            dst.relative_to(allowed)
        except ValueError as exc:
            raise ValueError("Employee document destination is outside managed attachments.") from exc

        shutil.copy2(src, dst)

        # Store a runtime-relative path so it can be reconstructed on every machine.
        rel = str(dst.relative_to(self._runtime_root.resolve()))
        with self._sf() as s:
            d = EmployeeDocument(
                employee_id=employee.id,
                document_type=document_type,
                original_filename=src.name,
                relative_path=rel,
                notes=notes,
            )
            s.add(d)
            s.commit()
            s.refresh(d)

        logger.info(
            "Employee document uploaded: employee_id=%s type=%s filename=%s "
            "runtime_path=%s repository_path=%s",
            employee.id,
            document_type,
            src.name,
            dst,
            self.get_repository_relative_path(d),
        )
        return d
