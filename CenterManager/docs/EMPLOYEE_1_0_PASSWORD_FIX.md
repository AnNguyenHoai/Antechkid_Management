# EMPLOYEE 1.0 / SECURITY REGRESSION FIX

## Fixed
`ChangePasswordDialog` still used direct legacy SHA-256 comparison after FINAL HARDENING 2 migrated passwords to bcrypt.

The dialog now uses `centermanager.security.password.verify_password()`, which supports:
- bcrypt password hashes
- legacy SHA-256 hashes for compatibility

The new password is still written using `hash_password()`, so successful password changes always persist a bcrypt hash.

## Validation
- `python -m compileall -q src` PASS
