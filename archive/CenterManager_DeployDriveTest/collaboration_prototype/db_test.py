# -*- coding: utf-8 -*-
"""
SQLite Behavior Test

Tests SQLite behavior in shared environment:
- Read-only access
- Read + Write access
- Write + Write conflicts
- WAL mode vs DELETE journal
- Database replacement (atomic?)
"""
import os
import time
import sqlite3
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional


class SQLiteTest:
    """
    Test SQLite behavior in a shared directory.
    Simulates multiple machines accessing the same database.
    """

    def __init__(self, db_path: Path, journal_mode: str = "WAL"):
        self.db_path = Path(db_path)
        self.journal_mode = journal_mode
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database with a test table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("INSERT OR IGNORE INTO test_table (id, value, updated_at) VALUES (1, 'initial', datetime('now'))")
        conn.commit()
        conn.close()

    def read_value(self) -> Optional[str]:
        """Read value from the database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
            cursor = conn.execute("SELECT value FROM test_table WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"[SQLiteTest] Read error: {e}")
            return None

    def write_value(self, value: str) -> bool:
        """Write a value to the database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
            conn.execute("UPDATE test_table SET value = ?, updated_at = datetime('now') WHERE id = 1", (value,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[SQLiteTest] Write error: {e}")
            return False

    def get_last_update(self) -> Optional[str]:
        """Get last update timestamp."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
            cursor = conn.execute("SELECT updated_at FROM test_table WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            print(f"[SQLiteTest] Get update error: {e}")
            return None

    def simulate_concurrent_writes(self, num_writers: int = 3, writes_per_writer: int = 5) -> Dict[str, Any]:
        """
        Simulate concurrent writes from multiple threads (machines).
        Returns results summary.
        """
        results = {"success": 0, "failures": 0, "errors": []}

        def writer(thread_id: int):
            for i in range(writes_per_writer):
                value = f"writer_{thread_id}_{i}"
                if self.write_value(value):
                    results["success"] += 1
                else:
                    results["failures"] += 1
                    results["errors"].append(f"Writer {thread_id} failed at iteration {i}")
                time.sleep(0.1)  # Small delay to simulate real-world

        threads = []
        for i in range(num_writers):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        return results

    def test_replacement(self) -> Dict[str, Any]:
        """
        Test atomic replacement of the database file.
        Simulates replacing the database with a new version.
        """
        results = {"atomic": False, "error": None}

        # Create a backup database
        backup_path = self.db_path.parent / f"{self.db_path.stem}_backup.db"
        try:
            # Simulate creating a new database file
            new_db_path = self.db_path.parent / f"{self.db_path.stem}_new.db"
            new_conn = sqlite3.connect(str(new_db_path))
            new_conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
            new_conn.execute("INSERT INTO test_table VALUES (1, 'new_data')")
            new_conn.commit()
            new_conn.close()

            # Attempt to replace the original database
            # In real Google Drive, this is a file copy/overwrite
            import shutil
            shutil.copy2(str(new_db_path), str(self.db_path))
            results["atomic"] = True

            # Cleanup
            new_db_path.unlink(missing_ok=True)

            # Verify the database is still valid
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("SELECT value FROM test_table WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] == "new_data":
                results["verified"] = True
            else:
                results["verified"] = False

        except Exception as e:
            results["error"] = str(e)

        return results