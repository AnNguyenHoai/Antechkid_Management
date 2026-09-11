from pathlib import Path


SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
    / "teacher_document_service.py"
)


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _TeacherRepository:
    def __init__(self):
        self.requested_ids = []

    def get_by_id(self, teacher_id):
        self.requested_ids.append(teacher_id)
        return type("Teacher", (), {"teacher_code": "T001", "deleted_at": None})()


class _TeacherDocumentRepository:
    def __init__(self):
        self.requested_ids = []
        self.requested_teachers = []

    def get_by_id(self, document_id):
        self.requested_ids.append(document_id)
        return None

    def get_by_teacher(self, teacher_id):
        self.requested_teachers.append(teacher_id)
        return []

    def add(self, document):
        return document

    def delete(self, document):
        return None


class _Provider:
    def __init__(self):
        self.teachers_repo = _TeacherRepository()
        self.documents_repo = _TeacherDocumentRepository()

    def teachers(self, session):
        return self.teachers_repo

    def teacher_documents(self, session):
        return self.documents_repo


class _Timeline:
    def log_event(self, **kwargs):
        return None


def _service(provider):
    from centermanager.services.teacher_document_service import TeacherDocumentService

    return TeacherDocumentService(
        _Session,
        _Timeline(),
        repository_provider=provider,
    )


def test_teacher_document_service_uses_injected_repository_provider():
    provider = _Provider()
    service = _service(provider)

    assert service.get_teacher_code(123) == "T001"
    assert service.get_documents_for_teacher(123) == []
    assert provider.teachers_repo.requested_ids == [123]
    assert provider.documents_repo.requested_teachers == [123]


def test_teacher_document_service_does_not_import_or_construct_concrete_repository():
    source = SERVICE_PATH.read_text(encoding="utf-8")

    assert "from centermanager.repositories.teacher_document_repository import" not in source
    assert "from centermanager.repositories.teacher_repository import" not in source
    assert "TeacherDocumentRepository(" not in source
    assert "TeacherRepository(" not in source
    assert "RepositoryProvider(" not in source
