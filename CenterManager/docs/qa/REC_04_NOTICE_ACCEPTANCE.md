# REC-04 — Recovery Review Must Not Block Operations

- Startup displays a nonmodal status/menu indicator.
- Shows signed pending Recovery Cases plus checked and unchecked manual-review archive folders.
- User chooses to open details; no forced modal, no automatic acknowledgement or deletion.
- The archive is NOT a second active workspace and is never used as a source for WRITE/publish.
- Raw journal/outbox plus WAL/DB remain available in the protected temporary archive for manual comparison with MAIN.

## Gate
test_rec04_nonmodal_notice.py and physical Windows UAT of pending/invalid/empty/corrupt Recovery archives and manually opening the backup folder.