# -*- coding: utf-8 -*-
"""
ReportService - derived local reports and pre-publication canonical metadata.
"""
import json
import logging
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union

from centermanager.core.paths import get_paths
from centermanager.core.current_user import get_current_user
from centermanager.models.report import Report
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.student_service import StudentService, StudentNotFoundError
from centermanager.services.parent_service import ParentService
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.session_service import SessionService
from centermanager.services.student_note_service import StudentNoteService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.income_service import IncomeService
from centermanager.export.pdf.student_report_generator import StudentReportGenerator

logger = logging.getLogger(__name__)


class ReportPreparationError(RuntimeError):
    """Required reports are incomplete; authoritative publication must wait."""


@dataclass(frozen=True)
class LocalReportArtifact:
    id: int
    student_id: int
    file_path: str
    report_type: str
    trigger_event: Optional[str]
    generated_by: str
    generated_at: datetime
    metadata_json: str

class ReportService:
    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        attendance_service: AttendanceService,
        session_service: SessionService,
        student_note_service: StudentNoteService,
        outstanding_service: OutstandingService,
        income_service: IncomeService,
        session_factory,
        repository_provider: Optional[RepositoryProvider] = None,
        write_guard=None,
    ) -> None:
        self._student_service = student_service
        self._parent_service = parent_service
        self._attendance_service = attendance_service
        self._session_service = session_service
        self._student_note_service = student_note_service
        self._outstanding_service = outstanding_service
        self._income_service = income_service
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()
        self._write_guard = write_guard
        self._prepared_student_ids = set()

        self._generator = StudentReportGenerator(
            student_service,
            parent_service,
            attendance_service,
            session_service,
            student_note_service,
            outstanding_service,
            income_service,
        )

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _default_report_path(self, student_id: int) -> Path:
        student = self._student_service.get_student_with_relations(student_id)
        reports_root = get_paths().runtime_root / "Reports" / "Student" / student.student_code
        output_path = reports_root / "StudentProfile.pdf"
        if not output_path.resolve().is_relative_to((get_paths().runtime_root / "Reports").resolve()):
            raise ValueError("Student report path escapes the Reports directory.")
        return output_path

    def _source_main_oid(self):
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        journal = WriteRecoveryJournal()
        document = journal.inspect()
        if document is not None:
            if document['status'] == 'OPEN':
                return document['base_main_oid']
            return document.get('published_oid')
        if (journal.repository / '.git').exists():
            return journal._git('rev-parse', 'HEAD')
        return None

    def _local_report(self, student_id: int, *, prepared=False) -> Optional[LocalReportArtifact]:
        if self._student_service is None:
            return None
        try:
            pdf = self._default_report_path(student_id)
            receipt = json.loads(pdf.with_suffix(".report.json").read_text(encoding="utf-8"))
            student = self._student_service.get_student_with_relations(student_id)
            created = student.created_at.isoformat() if student.created_at else None
            if (receipt["student_id"] != student_id or receipt["sha256"] != self._digest(pdf)
                    or receipt.get("student_created_at") != created
                    or (not prepared and receipt.get("source_main_oid") != self._source_main_oid())):
                return None
            relative = str(pdf.relative_to(get_paths().runtime_root))
            if receipt["file_path"] != relative:
                return None
            return LocalReportArtifact(
                id=-student_id, student_id=student_id, file_path=relative,
                report_type=receipt["report_type"], trigger_event=receipt["trigger_event"],
                generated_by=receipt["generated_by"],
                generated_at=datetime.fromisoformat(receipt["generated_at"]),
                metadata_json=json.dumps(receipt["metadata"], ensure_ascii=False),
            )
        except (OSError, ValueError, KeyError, TypeError, StudentNotFoundError):
            return None

    def generate_student_report(
        self, student_id: int, report_type: str = "manual",
        trigger_event: Optional[str] = None, generated_by: Optional[str] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Render a rebuildable local PDF/receipt without mutating SQLCipher.

        Manual READ-mode exports and daily reports use this API. Canonical SQL
        metadata is prepared separately under WRITE before the one MAIN push.
        """
        return self._generate(student_id, report_type, trigger_event, generated_by,
                              output_path, persist_metadata=False)

    def prepare_for_publication(self, student_ids) -> None:
        """Prepare each dirty aggregate once before snapshot/materialization."""
        self._prepared_student_ids = set()
        for student_id in sorted(set(student_ids)):
            try:
                self._generate(student_id, "latest", "student_updated", "system", None,
                               persist_metadata=True)
                self._prepared_student_ids.add(student_id)
            except StudentNotFoundError:
                # An aggregate edited then deleted has no required report.
                continue
            except Exception as exc:
                raise ReportPreparationError(
                    f"Report preparation failed for student ID {student_id}. "
                    "MAIN has not been published; local changes remain protected. Retry Finish Editing."
                ) from exc

    def verify_publication_reports(self) -> None:
        """Read-only delivery check after accepted core publication."""
        for student_id in self._prepared_student_ids:
            if self._local_report(student_id, prepared=True) is None:
                raise ReportPreparationError(
                    f"Core data was published, but report file for student ID {student_id} "
                    "is unavailable or changed. Regenerate the local report."
                )
            # Bind the derived receipt to the verified MAIN without writing SQL.
            from centermanager.platform.write_recovery import _json
            receipt_path = self._default_report_path(student_id).with_suffix(".report.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt['source_main_oid'] = self._source_main_oid()
            _json(receipt_path, receipt)

    def _generate(self, student_id, report_type, trigger_event, generated_by,
                  output_path, *, persist_metadata):
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        from centermanager.database.encryption import database_encryption_required
        journal = WriteRecoveryJournal()
        before = journal.begin_report_artifact_update()
        if persist_metadata:
            if self._write_guard is not None:
                self._write_guard.require_write()
            elif database_encryption_required() or before is not None:
                # A deployed metadata writer must be bound to the canonical guard.
                raise ReportPreparationError("Canonical WRITE guard is required for report metadata.")
        output_path = Path(output_path) if output_path is not None else self._default_report_path(student_id)
        runtime = Path(get_paths().runtime_root).resolve()
        output_path = output_path.resolve()
        if output_path.suffix.lower() != '.pdf':
            raise ValueError("Student reports must use a .pdf output path.")
        if not any(output_path.is_relative_to((runtime / folder).resolve()) for folder in ("Reports", "Export")):
            raise ValueError("Report output must be inside the runtime Reports or Export directory.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path = output_path.with_suffix(".report.json")
        unique = uuid.uuid4().hex
        candidate = output_path.with_name(f".{output_path.stem}-{unique}.tmp.pdf")
        candidate_receipt = receipt_path.with_name(f".{receipt_path.name}-{unique}.tmp")
        backups = {}
        installed = []
        try:
            self._generator.generate(student_id, candidate)
            with candidate.open("r+b") as stream:
                if stream.read(5) != b"%PDF-":
                    raise ReportPreparationError("Report generator did not produce a valid PDF.")
                stream.flush()
                os.fsync(stream.fileno())
            generated_at = datetime.now()
            actor = generated_by or (get_current_user().full_name if get_current_user() else "system")
            metadata = {"center_name": "AN TECHKIDS", "academic_year": "2026-2027"}
            student = self._student_service.get_student_with_relations(student_id)
            receipt = dict(student_id=student_id,
                           student_created_at=student.created_at.isoformat() if student.created_at else None,
                           source_main_oid=self._source_main_oid(),
                           file_path=str(output_path.relative_to(runtime)),
                           report_type=report_type, trigger_event=trigger_event, generated_by=actor,
                           generated_at=generated_at.isoformat(), metadata=metadata,
                           sha256=self._digest(candidate))
            with candidate_receipt.open("x", encoding="utf-8") as stream:
                json.dump(receipt, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            for destination, temporary in ((output_path, candidate), (receipt_path, candidate_receipt)):
                if destination.exists():
                    backup_root = get_paths().temp_dir
                    backup_root.mkdir(parents=True, exist_ok=True)
                    backup = backup_root / f"report-{unique}-{destination.name}.previous"
                    shutil.copy2(destination, backup)
                    backups[destination] = backup
                from centermanager.platform.write_recovery import _install
                _install(temporary, destination)
                installed.append(destination)
            if persist_metadata:
                # Rendering may be slow; recheck the canonical local WRITE gate
                # immediately before opening the metadata transaction as well.
                if self._write_guard is not None:
                    self._write_guard.require_write()
                with self._session_factory() as session:
                    repo = self._repository_provider.reports(session)
                    for existing in repo.get_by_student(student_id):
                        repo.delete(existing)
                    report = Report(student_id=student_id, file_path=receipt["file_path"],
                                    report_type=report_type, trigger_event=trigger_event,
                                    generated_by=actor, generated_at=generated_at,
                                    metadata_json=json.dumps(metadata, ensure_ascii=False))
                    repo.add(report)
                    session.commit()
            journal.finish_report_artifact_update(before, (output_path, receipt_path))
            return output_path
        except Exception:
            # Preserve the previous good derived pair on render/file/SQL failure.
            # E1B-1 recovery captures and authoritative data are never removed.
            for destination in reversed(installed):
                if destination in backups:
                    os.replace(backups.pop(destination), destination)
                else:
                    destination.unlink(missing_ok=True)
            raise
        finally:
            candidate.unlink(missing_ok=True)
            candidate_receipt.unlink(missing_ok=True)
            for backup in backups.values():
                backup.unlink(missing_ok=True)

    def get_student_reports(self, student_id: int) -> List[Union[Report, LocalReportArtifact]]:
        local = self._local_report(student_id)
        if local is not None:
            return [local]
        with self._session_factory() as session:
            repo = self._repository_provider.reports(session)
            return repo.get_by_student(student_id)

    def get_report_file_path(self, report_id: int) -> Optional[Path]:
        if report_id < 0:
            local = self._local_report(-report_id)
            return get_paths().runtime_root / local.file_path if local else None
        with self._session_factory() as session:
            repo = self._repository_provider.reports(session)
            report = repo.get_by_id(report_id)
            if report is None:
                return None
            path = get_paths().runtime_root / report.file_path
            if path.with_suffix(".report.json").exists() and self._local_report(report.student_id) is None:
                return None  # An older generation must never masquerade as current.
            return path

    def delete_report(self, report_id: int) -> None:
        if self._write_guard is not None:
            self._write_guard.require_write()
        if report_id < 0:
            local = self._local_report(-report_id)
            if local is None:
                return
            file_path = get_paths().runtime_root / local.file_path
            with self._session_factory() as session:
                repo = self._repository_provider.reports(session)
                for existing in repo.get_by_student(local.student_id):
                    repo.delete(existing)
                session.commit()
            file_path.unlink(missing_ok=True)
            file_path.with_suffix(".report.json").unlink(missing_ok=True)
            return
        with self._session_factory() as session:
            repo = self._repository_provider.reports(session)
            report = repo.get_by_id(report_id)
            if report is None:
                return
            file_path = get_paths().runtime_root / report.file_path
            if file_path.exists():
                file_path.unlink()
            repo.delete(report)
            session.commit()

    def report_exists(self, student_id: int, trigger_event: str) -> bool:
        """Check the current local artifact, with legacy SQL metadata fallback."""
        local = self._local_report(student_id)
        if local is not None:
            return local.trigger_event == trigger_event
        with self._session_factory() as session:
            repo = self._repository_provider.reports(session)
            return repo.get_by_student_and_trigger(student_id, trigger_event) is not None

    def report_exists_on_date(self, student_id: int, trigger_event: str, target_date) -> bool:
        """Check whether this student already has this trigger's report on target_date."""
        local = self._local_report(student_id)
        if local is not None:
            return local.trigger_event == trigger_event and local.generated_at.date() == target_date
        with self._session_factory() as session:
            repo = self._repository_provider.reports(session)
            return repo.exists_for_student_trigger_on_date(
                student_id, trigger_event, target_date
            )
