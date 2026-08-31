"""Final Hardening 4 verification runner."""
import subprocess, sys
commands=[
 [sys.executable,"-m","compileall","-q","src"],
 [sys.executable,"-m","pytest","-q","tests/test_migrations.py","tests/test_admin_10_foundation.py","tests/test_admin_11_user_account_management.py","tests/test_admin_12_role_permission_management.py","tests/test_admin_14_audit_trail.py","tests/test_admin_15_configuration_lifecycle.py","tests/test_admin_16_system_operations.py","tests/test_admin_17_backup_recovery.py","tests/test_admin_18_integration_hardening.py"],
]
for command in commands:
    result=subprocess.run(command)
    if result.returncode:
        raise SystemExit(result.returncode)
print("FINAL HARDENING 4 verification passed.")
