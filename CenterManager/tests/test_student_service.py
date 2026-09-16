# --- Transaction Rollback Test ---

def test_transaction_rollback(test_db_path):
    """
    Prove that if an exception occurs after data is flushed inside a transaction,
    the transaction is rolled back and no partial data is committed.
    """
    service = _create_service(test_db_path)

    # Monkeypatch the repository's add method to simulate failure after flush.
    # The repository intentionally exposes no public SQLAlchemy Session accessor,
    # so use the repository's own transaction-scoped operation instead of reaching
    # through the repository boundary.
    original_add = StudentRepository.add

    def failing_add(repo_self, entity):
        original_add(repo_self, entity)
        repo_self.flush()
        # Now simulate an error after flush, before commit.
        raise RuntimeError("Forced transaction failure")

    with patch.object(StudentRepository, 'add', failing_add):
        # Attempt to create student, should fail
        with pytest.raises(RuntimeError, match="Forced transaction failure"):
            service.create_student(full_name="Rollback Test")

    # Verify no student was created
    students = service.list_students()
    assert len(students) == 0, "Student should not exist after rollback"

    # Also verify directly in DB
    with service._session_factory() as session:
        count = session.query(Student).filter(Student.full_name == "Rollback Test").count()
        assert count == 0