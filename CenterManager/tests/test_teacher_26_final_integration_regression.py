from datetime import date

from centermanager.database.engine import create_engine_for_path
from sqlalchemy.orm import sessionmaker
from centermanager.models.teacher import Teacher
from centermanager.services.teacher_service import TeacherService


def _teacher_service(test_db):
    engine = create_engine_for_path(test_db)
    return TeacherService(sessionmaker(bind=engine, autocommit=False, autoflush=False))


def _create_teacher(teacher_service):
    return teacher_service.create_teacher(
        full_name="Integration Teacher",
        email="integration@example.com",
        phone="0900000000",
        join_date=date(2026, 1, 1),
        status=Teacher.STATUS_ACTIVE,
    )


def test_teacher_lifecycle_create_edit_archive_restore_and_archived_queries(test_db):
    service = _teacher_service(test_db)
    created = _create_teacher(service)

    assert created.deleted_at is None
    assert [t.id for t in service.list_teachers()] == [created.id]

    updated = service.update_teacher(
        created.id,
        full_name="Integration Teacher Updated",
        status=Teacher.STATUS_INACTIVE,
    )
    assert updated.full_name == "Integration Teacher Updated"
    assert updated.status == Teacher.STATUS_INACTIVE

    service.delete_teacher(created.id)

    assert service.list_teachers() == []
    archived = service.list_archived_teachers()
    assert [t.id for t in archived] == [created.id]

    archived_teacher = service.get_archived_teacher(created.id)
    assert archived_teacher.deleted_at is not None
    assert archived_teacher.full_name == "Integration Teacher Updated"

    service.restore_teacher(created.id)

    restored = service.get_teacher_with_details(created.id)
    assert restored.deleted_at is None
    assert restored.full_name == "Integration Teacher Updated"
    assert restored.status == Teacher.STATUS_INACTIVE


def test_teacher_assignment_relationship_is_available_from_details_and_list(test_db):
    service = _teacher_service(test_db)
    teacher = _create_teacher(service)

    details = service.get_teacher_with_details(teacher.id)
    assert details.assigned_classes == []
    assert service.list_teachers()[0].assigned_classes == []


def test_archived_teacher_is_not_returned_by_current_details_lookup(test_db):
    service = _teacher_service(test_db)
    teacher = _create_teacher(service)
    service.delete_teacher(teacher.id)

    try:
        service.get_teacher_with_details(teacher.id)
    except Exception:
        pass
    else:
        raise AssertionError("Archived teacher must not be returned by current lookup")

    assert service.get_archived_teacher(teacher.id).id == teacher.id
