CENTERMANAGER — SPRINT 0.1 FIX ROUND 1

Status: REQUIRED
Reason: Technical Lead Review FAILED

Do NOT begin Sprint 0.2.

Fix only the issues listed below.

1. Fix MainWindow typing error

File:
src/centermanager/ui/main_window.py

Optional is referenced but not imported.

Application must successfully import and launch after dependencies are installed.


2. Fix test isolation

Current tests must NEVER modify/delete the real project runtime directory.

All filesystem-mutating tests must operate under pytest tmp_path or another isolated temporary runtime.

Specifically ensure tests cannot:

- delete real runtime/
- delete real Config/config.json
- modify production config
- create test artifacts in production runtime

Fix singleton reset/override correctly at module level.

Tests must prove isolation.


3. Remove duplicated runtime structure

Remove:

src/runtime/

There must be only:

<project_root>/runtime/


4. Restore runtime configuration

Ensure:

runtime/Config/config.json

exists in the clean project baseline with:

{
    "application": {
        "name": "CenterManager",
        "version": "0.1.0"
    }
}


5. Complete package structure

Add:

src/centermanager/export/excel/__init__.py


6. Fix incorrect PDF package docstring

src/centermanager/export/pdf/__init__.py

must describe PDF functionality, not Excel.


7. Clean documentation formatting

Review:

README.md
docs/ARCHITECTURE.md
docs/DEVELOPMENT_GUIDE.md
docs/PROJECT_CONTEXT.md

Remove leaked formatting markers such as standalone:

text
bash
python

where they are intended to be Markdown code fences.

Ensure README clean-environment instructions are readable and executable.


8. Verify clean environment

Create a fresh virtual environment.

Run:

pip install -r requirements.txt
pip install -r requirements-dev.txt

Then:

pytest

All tests must PASS.

Then:

python run.py

Confirm the PySide6 MainWindow launches successfully.


9. Clean delivery

Do not include generated development artifacts in the final source package:

.venv/
__pycache__/
.pytest_cache/
*.pyc

Do not remove required runtime directory placeholders/config.


10. Required report

Return:

A. Files modified
B. Files added
C. Files removed
D. Root cause of test-isolation bug
E. Test isolation solution
F. pytest actual result
G. python run.py actual result
H. Remaining known issues

Do NOT implement any Sprint 0.2 functionality.