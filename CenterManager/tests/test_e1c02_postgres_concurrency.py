"""E1C PostgreSQL contention release gates.

Requires a disposable database URL in E1C_TEST_POSTGRES_URL. Never run with
production credentials. Each test creates a unique isolated schema.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from centermanager.coordinator.authority import Coordinator, CoordinatorError, Base


@pytest.fixture
def postgres():
    url = os.environ.get("E1C_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL E1C_TEST_POSTGRES_URL")
    if not url.startswith(("postgresql+psycopg://", "postgresql://")):
        pytest.fail("E1C integration URL must use PostgreSQL")
    schema = "e1c_qa_" + uuid.uuid4().hex[:16]
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, pool_pre_ping=True,
                           connect_args={"options": f"-csearch_path={schema}"},
                           isolation_level="READ COMMITTED")
    try:
        Base.metadata.create_all(engine)
        coordinator = Coordinator(engine)
        coordinator.bootstrap("repo", "0" * 64)
        yield coordinator
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_two_competing_acquires_have_single_owner(postgres):
    barrier = Barrier(2)
    def acquire(index):
        barrier.wait(timeout=15)
        try:
            return postgres.command("repo", f"user{index}", f"grant{index}",
                                    "acquire", expected_revision=0,
                                    session_id=f"session{index}")
        except CoordinatorError as err:
            return err.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(acquire, (0, 1)))
    assert sum(isinstance(value, dict) for value in outcomes) == 1, outcomes
    assert sum(value in ("LEASE_HELD", "REVISION_CONFLICT") for value in outcomes) == 1
    assert postgres.state("repo")["revision"] == 1


def test_concurrent_publish_and_revoke_serialize(postgres):
    grant = postgres.command("repo", "alice", "grant", "acquire",
                             expected_revision=0, session_id="A")
    postgres.register_candidate("repo", "alice", "candidate", "a" * 64, 1,
                                "synthetic", verified=True)
    barrier = Barrier(2)
    def publish():
        barrier.wait(timeout=15)
        try:
            return postgres.command("repo", "alice", "publish", "publish",
                                    session_id="A", epoch=grant["epoch"],
                                    expected_revision=1, expected_accepted_sha="0"*64,
                                    candidate_id="candidate")
        except CoordinatorError as error:
            return error.code
    def revoke():
        barrier.wait(timeout=15)
        try:
            return postgres.command("repo", "admin", "revoke", "revoke",
                                    admin_authorized=True, expected_revision=1,
                                    expected_epoch=1, target_session_id="A")
        except CoordinatorError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result_a = pool.submit(publish)
        result_b = pool.submit(revoke)
        outcomes = [result_a.result(timeout=30), result_b.result(timeout=30)]
    assert sum(isinstance(x, dict) for x in outcomes) == 1, outcomes
    assert sum(x in ("REVISION_CONFLICT", "STALE_SESSION") for x in outcomes) == 1
    assert postgres.state("repo")["revision"] == 2
    if isinstance(outcomes[0], dict):
        assert postgres.state("repo")["accepted_sha"] == "a"*64
    else:
        assert postgres.state("repo")["accepted_sha"] == "0"*64


def test_postgresql_clock_is_not_python_process_clock(postgres, monkeypatch):
    import centermanager.coordinator.authority as module
    class BrokenClock:
        @staticmethod
        def now(*args, **kwargs):
            raise AssertionError("application wall clock must not be consulted")
    monkeypatch.setattr(module, "datetime", BrokenClock)
    granted = postgres.command("repo", "alice", "grant", "acquire",
                               expected_revision=0, session_id="A")
    assert granted["revision"] == 1
