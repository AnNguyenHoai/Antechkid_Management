# EP-ARCH-04.4 — Production Fix

The post-merge regression exposed two existing boundary violations:

- `AuditLogRepository.persist()` committed its own transaction.
- `BaseRepository` exposed a public raw SQLAlchemy `session` accessor.

The fix restores the intended architecture:

- repository persistence performs `add` / `flush` / `refresh` only;
- `AuditService.record()` owns `session.commit()`;
- `BaseRepository` keeps the SQLAlchemy session private.

No new transaction policy or business behavior is introduced.