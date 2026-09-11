# FINAL HARDENING 3 — Backup & Recovery

Implemented integrity validation, SHA-256 checksums, SQLite integrity checks, managed backup path boundaries, format-version validation, and replace (not merge) metadata restore semantics. Restore validates the backup before changing runtime state and uses temporary files/directories to reduce partial-restore risk.
