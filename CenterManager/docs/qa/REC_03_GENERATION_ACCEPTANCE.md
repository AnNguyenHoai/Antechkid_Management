# REC-03 — New CLEAN Receipt for One Authoritative MAIN

- `StartupSynchronization` only issues an ephemeral, single-process capability after exact remote MAIN and verified archive.
- The active DB is installed from Git MAIN, SQLCipher and Alembic verified before login.
- If an old journal exists, its ORIGINAL bytes are archived and checksum-verified. New receipt records accepted-main OID, current DB fingerprint and archive pointer without changing old evidence.
- No receipt can be issued when backup missing/tampered, remote MAIN changed, DB/WAL uncertain, Git worktree dirty or schema migration failed.
- Existing remote lease, READ/WRITE mutation permits and publication CAS remain unchanged.
- `record_verified_manual_reset` is not a mechanism for pretending legacy data was published.
- The routine also covers the incident where no DB or journal exists but business material prevents `fresh_install` (machine with READ but cannot Start Editing).

## Gate
test_rec03_single_main_acceptance.py, test_rv05_recovery_to_new_write.py, Git MAIN two-machine EXE UAT, denied stale publish and confirmed Finish Editing. Do not merge before REC-02 and full CI.