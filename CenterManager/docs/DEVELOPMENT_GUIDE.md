# DEVELOPMENT_GUIDE – CenterManager

This guide provides everything a developer needs to set up, run, test, and extend CenterManager.

---

## Environment Setup

### Prerequisites
- Python 3.9 or higher
- pip (package installer)

### Create Virtual Environment
```
python -m venv .venv
Activate it:

Linux/macOS: source .venv/bin/activate

Windows: .venv\Scripts\activate

Install Dependencies
Runtime Dependencies

pip install -r requirements.txt
Development Dependencies

pip install -r requirements-dev.txt
Run the Application

python run.py
A minimal PySide6 window titled "CenterManager" should appear.

Run Tests
All tests are written with pytest.


pytest
Expected output:


============================= test session starts ==============================
collected 12 items

tests/test_config.py ....                                                 [ 33%]
tests/test_paths.py ...                                                   [ 58%]
tests/test_smoke.py .....                                                 [100%]

============================== 12 passed in 0.45s ==============================
For verbose output:


pytest -v
To run a specific test file:


pytest tests/test_paths.py
Coding Rules
Must Use
Python type hints for all function signatures.

pathlib.Path for all filesystem operations.

Clear naming: functions should be verbs (get_student), classes nouns (StudentService).

Small, focused classes/functions: Single Responsibility Principle.

Docstrings for public APIs (Google or NumPy style).

Avoid
God classes – keep classes under ~300 lines (guideline).

Global mutable state – except for the approved singletons in core/.

Hardcoded absolute paths – always use core.paths.

Business logic inside UI – delegate to Services.

SQL inside UI – use Repositories.

Catch‑all exception swallowing – except Exception: pass is forbidden.

Premature abstraction – YAGNI.

Principles
KISS: Keep It Simple, Stupid.

YAGNI: You Ain't Gonna Need It.

Separation of Concerns.

Architecture Rules
Layer Violations
❌ UI → Database (direct)

❌ UI → Repository

✅ UI → Service

❌ Service → Database (direct)

✅ Service → Repository

✅ Repository → Database (SQLAlchemy)

Accessing Paths
Always use the global paths:

python
from centermanager.core.paths import get_paths, database_dir, export_dir

paths = get_paths()
db_path = paths.database_dir / "center.db"
# or
db_path = database_dir() / "center.db"
Accessing Configuration
python
from centermanager.core.config import get_config

config = get_config()
app_name = config.get("application.name")
Logging
Use logging.getLogger(__name__) and log appropriately:

python
import logging
logger = logging.getLogger(__name__)

logger.info("Student saved")
logger.error("Failed to export PDF", exc_info=True)
Adding a Future Module
To add a new business feature (e.g., attendance):

Create a new package under src/centermanager/modules/attendance/.

Inside, create the typical layers if needed:

models.py (SQLAlchemy models)

services.py (business logic)

repositories.py (data access)

ui/ (PySide6 widgets)

Register the module in the main UI (e.g., add a menu item in MainWindow).

Update the database schema (add migrations – future sprint).

Write tests in tests/modules/test_attendance.py.

Never modify core/ for business‑specific logic.

PyInstaller Packaging (Future)
When the application is ready for distribution, run:


pyinstaller centermanager.spec
The runtime/ directory will be created relative to the executable. Ensure all paths are resolved dynamically using core.paths – no hardcoded paths.

Troubleshooting
Issue	Solution
ModuleNotFoundError: No module named 'centermanager'	Ensure you are running python run.py from the project root, or check that src/ is in sys.path.
PermissionError on runtime directories	Check write permissions for the project folder.
PySide6 import errors	Reinstall PySide6: pip install --force-reinstall PySide6
Tests fail with "config.json not found"	The tests use a temporary runtime; ensure you have pytest installed and are running from the root.
Logging does not write to file	Check that runtime/Logs/ exists and is writable. setup_logging creates it.
