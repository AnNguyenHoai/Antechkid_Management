from pathlib import Path

SERVICE = Path("src/centermanager/services/teacher_document_service.py")


def test_upload_uses_unique_storage_name_and_compensation():
    text = SERVICE.read_text(encoding="utf-8")
    assert "uuid.uuid4().hex" in text
    assert "except Exception:" in text
    assert "dest_path.unlink()" in text
    assert "source_path.is_file()" in text


def test_delete_commits_before_physical_delete():
    text = SERVICE.read_text(encoding="utf-8")
    start = text.index("    def delete_document(")
    body = text[start:]
    assert body.index("session.commit()") < body.index("if file_path.exists()")
    assert "try:" in body
    assert "except OSError:" in body


def test_delete_only_removes_empty_teacher_folder():
    text = SERVICE.read_text(encoding="utf-8")
    assert "not any(parent.iterdir())" in text


def test_upload_removes_empty_teacher_folder_after_failed_persistence():
    text = SERVICE.read_text(encoding="utf-8")
    assert "not any(teacher_folder.iterdir())" in text
