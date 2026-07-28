CENTERMANAGER
SPRINT 0.1R2 — TEST SAFETY PATCH

Technical Lead Review Result: R1 FAILED

Do NOT begin Sprint 0.2.

Only fix the following issues.


1. CRITICAL — ALL filesystem-mutating tests must use isolated runtime

Current temp_runtime fixture correctly overrides:

centermanager.core.paths._paths

but filesystem tests are still using clean_paths.

Therefore tests are still modifying the real project runtime.


REQUIREMENT:

Any test that creates, modifies, deletes, or overwrites runtime files/directories MUST use:

temp_runtime

not:

clean_paths


This includes at minimum:

test_config_uses_default_when_missing
test_config_save_and_load
test_init_config_creates_default_if_missing
test_ensure_directories_creates_all

Review ALL tests for the same problem.


2. Remove unsafe singleton reset logic

Do not use:

from centermanager.core.paths import _paths
from centermanager.core.config import _config

followed by:

global _paths
_paths = None

This does NOT reset the singleton in the original module.

Always modify the module itself:

from centermanager.core import paths as paths_module
from centermanager.core import config as config_module

paths_module._paths = ...
config_module._config = ...


3. Add explicit production-runtime protection test

Add a test proving that filesystem tests do NOT modify:

<project_root>/runtime

Recommended approach:

- Capture production runtime state before isolated operation.
- Perform destructive operations using temp_runtime.
- Verify production runtime remains unchanged.

At minimum ensure the real:

runtime/Config/config.json

is not deleted or modified by tests.


4. Restore baseline configuration

Ensure final source package contains:

runtime/Config/config.json

with:

{
    "application": {
        "name": "CenterManager",
        "version": "0.1.0"
    }
}


5. Clean delivery artifacts

Remove before packaging:

__pycache__/
*.pyc
.pytest_cache/
.venv/

Do not remove required runtime structure.


6. Verification

Run from clean environment:

pytest

ALL tests must PASS.

Then verify AFTER pytest:

runtime/Config/config.json

still exists and its content is unchanged.


7. Application verification

Run:

python run.py

Confirm MainWindow launches.


8. Required report

Return:

A. Root cause
B. Files modified
C. Test isolation implementation
D. New safety test
E. pytest result
F. Confirmation that runtime/Config/config.json survives pytest unchanged
G. python run.py result
H. Remaining known issues

Do NOT implement Sprint 0.2 functionality.