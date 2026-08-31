# FINAL HARDENING 2 — Security
- Removed plaintext Git token from tracked docs/config.json.
- Added bcrypt password hashing.
- Legacy SHA-256 passwords remain accepted once and are transparently upgraded to bcrypt after successful login.
- New users, resets, password changes, and default admin creation use bcrypt.
- Auto-generated temporary passwords are returned to the create-user UI as a transient value, never reconstructed from password_hash.
- Rotate/revoke any previously exposed Git token.
