"""REC-635 financial review addenda: natural ID crosswalk and ledger movement."""
import sqlite3

from centermanager.platform.recovery_business_compare import (
    compare_identity_and_monthly_plans, outstanding_coverage, wallet_movements,
)


def _new():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE students (id INTEGER PRIMARY KEY,student_code TEXT,full_name TEXT,
                               status TEXT,deleted_at TEXT);
        CREATE TABLE classes (id INTEGER PRIMARY KEY,name TEXT,course TEXT,
                              status TEXT,course_fee INTEGER,planned_sessions INTEGER,
                              deleted_at TEXT);
        CREATE TABLE monthly_tuition_plans (id INTEGER PRIMARY KEY,class_id INTEGER,
                              month TEXT,version INTEGER,monthly_fee_vnd INTEGER,
                              schedule_version TEXT,status TEXT);
        CREATE TABLE incomes (id INTEGER PRIMARY KEY,amount REAL,payment_method TEXT,
                              status TEXT,deleted_at TEXT);
        CREATE TABLE expenses (id INTEGER PRIMARY KEY,amount REAL,payment_method TEXT,
                              status TEXT,deleted_at TEXT);
    """)
    return db


def test_unique_cross_generation_class_name_and_student_code():
    old, main = _new(), _new()
    old.execute("INSERT INTO students VALUES (1,'ST-0001','An','ACTIVE',NULL)")
    main.execute("INSERT INTO students VALUES (900,'ST-0001','An','ACTIVE',NULL)")
    old.execute("INSERT INTO classes VALUES (2,'K3 Python','Python','ACTIVE',1000000,8,NULL)")
    main.execute("INSERT INTO classes VALUES (80,'K3 Python','Python','ACTIVE',1000000,8,NULL)")
    old.execute("INSERT INTO monthly_tuition_plans VALUES (3,2,'2026-11-01',1,1200000,'s1','ACTIVE')")
    main.execute("INSERT INTO monthly_tuition_plans VALUES (99,80,'2026-11-01',1,1200000,'s1','ACTIVE')")
    rows = compare_identity_and_monthly_plans(old, main)["findings"]
    assert len(rows) == 3
    assert all(x["status"] == "PRESENT_IDENTICAL" for x in rows)
    assert rows[0]["main_row_id"] == 900
    assert rows[2]["main_row_id"] == 99


def test_duplicated_class_identity_stays_unknown():
    old, main = _new(), _new()
    old.execute("INSERT INTO classes VALUES (1,'Python','Python','ACTIVE',1000000,8,NULL)")
    main.execute("INSERT INTO classes VALUES (8,'Python','Python','ACTIVE',1000000,8,NULL)")
    main.execute("INSERT INTO classes VALUES (9,'Python','Python','ACTIVE',1000000,8,NULL)")
    old.execute("INSERT INTO monthly_tuition_plans VALUES (3,1,'2026-11-01',1,1200000,'s1','ACTIVE')")
    findings = compare_identity_and_monthly_plans(old, main)["findings"]
    assert next(x for x in findings if x["entity"] == "classes")["status"] == "UNKNOWN"
    assert next(x for x in findings if x["entity"] == "monthly_tuition_plans")["status"] == "UNKNOWN"


def test_wallet_is_movement_only_and_excludes_non_realized():
    db = _new()
    db.execute("INSERT INTO incomes VALUES (1,1000000,'Cash','ACTIVE',NULL)")
    db.execute("INSERT INTO incomes VALUES (2,500000,'Bank','VOIDED',NULL)")
    db.execute("INSERT INTO expenses VALUES (1,120000,'Cash','Completed',NULL)")
    db.execute("INSERT INTO expenses VALUES (2,100000,'Bank','Pending',NULL)")
    result = wallet_movements(db)
    assert result["status"] == "PARTIAL_MOVEMENT_ONLY"
    assert result["cash_delta"] == "880000.00"
    assert result["bank_delta"] == "0.00"
    assert "KHÔNG phải số dư" in result["warning"]


def test_unknown_wallet_alias_prevents_false_totals():
    db = _new()
    db.execute("INSERT INTO incomes VALUES (1,1000000,'CrypticMethod','ACTIVE',NULL)")
    assert wallet_movements(db)["status"] == "UNKNOWN"
    assert outstanding_coverage()["status"] == "UNKNOWN"


def test_schema_drift_never_creates_fake_monthly_plan_match():
    old = sqlite3.connect(":memory:")
    main = _new()
    findings = compare_identity_and_monthly_plans(old, main)["findings"]
    assert all(x["status"] == "UNKNOWN" for x in findings)
