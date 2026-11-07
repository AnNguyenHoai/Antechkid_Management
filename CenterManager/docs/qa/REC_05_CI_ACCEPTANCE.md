# REC-05 — Single Active Git MAIN Fault-Injection and CI

Automatic tests cover pre-copy failure; checksum mismatch; tampered WAL/receipt; malformed old Recovery; independent MAIN OID mismatch; disk-full when sealing new CLEAN receipt; restart idempotence; and the existing real Git+SQLCipher RV-05 integration test that proves earlier local unaccepted business rows do NOT appear on MAIN.

Expected source of truth: Git MAIN only; active database: runtime/Database/center.db; recovery: immutable historical log and temporary copy in sibling .write-recovery/manual-review.

No runtime multiplexer, alternate active DB, auto merge, or recovery publish. PR stays Draft until all three Windows pytest shards on HEAD PASS and two-machine Windows EXE acceptance passes.