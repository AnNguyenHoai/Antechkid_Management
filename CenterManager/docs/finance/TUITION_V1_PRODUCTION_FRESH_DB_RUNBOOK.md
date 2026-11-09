# Tuition Engine V1 — New SQLCipher Production Workspace (November 2026)

**Status: Production candidate, subject to CI, encrypted Windows/EXE physical UAT, and founder release sign-off.**
This runbook is for a **new empty** database; it NEVER rewrites the existing AnTechKids production database or its history.

## Business contract
1. In the new DB, create a class with billing policy **Theo tháng (lớp mới)** and monthly fee in whole VND. Historic classes created without this policy stay **COURSE**.
2. Enter class start date in November 2026 if commencing the November 2026 monthly billing period. Course duration and *Planned Sessions* must cover every weekly session over the selected period (the schedule generator rejects a short upper bound).
3. In **Class Detail → Học phí tháng**, select teaching weekdays (e.g., Saturday + Sunday) and press **Tạo đủ buổi theo lịch tuần**. A class with 2 weekend sessions/week has **9 original lessons in November 2026**. Confirm original calendar and allocation.
4. Choose **Xem trước → Lưu bản nháp → Kích hoạt** for each month. The sum of immutable allocations equals the monthly fee. A new monthly class can't activate an incomplete calendar.
5. **For each class, generate and ACTIVATE its initial November plan before recording that class's Enrollment, Income, Attendance or completed Session.** Classes may be entered sequentially even after another MONTHLY class has students. The current-month exception works only when ALL classes in the workspace are newly created MONTHLY classes whose first period is the same current month, and there are no historical/unassigned receipts. Past-month activation is never allowed.
6. Enroll students AFTER their class plan is ACTIVE. In the Enrollment pricing dialog for a MONTHLY class, explicitly select each learner's **actual joining date**, even if importing records later. The UI starts at the class start date rather than silently assuming today's date; use 01/11/2026 for a learner already attending on 01/11 and 09/11/2026 only for a genuinely later join. The first-month preview shows how many original sessions remain and the exact allocated first-month amount. A multi-select list asks each learner individually. Enrollment and automatic MONTHLY term are saved **atomically**; no manual legacy migration privilege is needed.
7. Once enrolled, backfill teaching session status and attendance from the true historical records, then enter Income with the **true actual payment date** and relevant tuition billing period. Income uses **Theo tháng** or **Theo quý (3 tháng)**; quarterly preview requires 3 sequential ACTIVE monthly plans and posts ONE actual Income. Do not invent an Income, a completed class session, or attendance from the planned schedule. Centre cancellations require their approved monthly billing-outcome command; ordinary student absence remains billable with separately arranged makeup.
8. Verify each learner's Tuition Detail, outstanding and wallet vs the paper/bank records and then Finish Editing / restart to check Git MAIN persistence. Do not begin new real operations until account balances are reconciled.

**Concrete 4-month weekend example:** For a class beginning **01/11/2026**, with **Saturday + Sunday**, there are **9 lessons in Nov, 8 in Dec, 10 in Jan 2027, and 8 in Feb 2027** (**35 total**). Set **Planned Sessions ≥ 35** before generating; using 32 (the legacy 8-per-month estimate) will be refused to prevent session-range truncation. Tuition is fixed per MONTH, regardless of 8/9/10 lessons. For a learner joining 01/11, the November charge is the whole 700,000 VND; a learner joining 09/11 is charged only the six 14–29 Nov sessions from the immutable allocation.

**What it does not do:** automatically create a Git database from a totally empty GitHub repository at normal application startup; bypass existing historic finance reconciliation; open the earlier production database for current-month repricing; or retroactively create attendance/receipts.

## Create a fresh encrypted repository safely (Windows only)

**Prerequisites:** production-candidate EXE ZIP for the exact accepted GitHub source SHA; Windows 10/11 with Python 3.10 and project source dependencies installed; Git; a new **PRIVATE, EMPTY** GitHub repository named, for example, `AnNguyenHoai/Antechkid_CenterManager_DB_MonthlyV1`, with **NO README/initial commit**. Never use `Antechkid_CenterManager_DatabaseOfficial` as the destination for this reset. Never use the publicly visible `Antechkid_CenterManager_DB_Test` unless first made PRIVATE.

**Do not copy `center.db` alone.** Production startup requires both a valid encrypted `database/center.db` AND its signed SEC-05 `database/center.db.identity.json`, plus a canonical repository `manifest.json`. Plain copying the database from another Windows account also loses the DPAPI workspace key.

A preinstalled, audited first-run helper already creates a **disposable** fresh SQLCipher DB, its DPAPI key, seeds an administrator, writes the signed SEC-05 identity, constructs a canonical manifest, verifies READY, and commits everything to a **LOCAL bare Git remote**. From the checked-out CenterManager source root, use a short path to avoid Windows MAX_PATH errors:

```powershell
cd C:\ATK-SOURCE\CenterManager
python scripts/prepare_sec06_isolated_uat.py --package "C:\ATK-RELEASE" --target "C:\ATK-BOOT" --remote "C:\ATK-LOCAL-BARE.git"
# Review the dry run, then on a BRAND NEW workstation/workspace only:
python scripts/prepare_sec06_isolated_uat.py --package "C:\ATK-RELEASE" --target "C:\ATK-BOOT" --remote "C:\ATK-LOCAL-BARE.git" --apply --confirm PREPARE-ISOLATED-SEC06-UAT
```

`--package` points to the extracted directory containing `CenterManager.exe`, *not* the outer downloaded ZIP. All three directories must satisfy the script's nonexistence/path checks. The helper is an **isolated generator** and intentionally configures a local file:// Git remote, not production credentials.

Before publication to GitHub, validate the signed pair exists in `C:\ATK-BOOT\runtime\repository\database\`. Create the new PRIVATE remote manually with **no initial README**. Then, from the prepared workspace (after verifying the destination URL is the new private repo, never the old production repo):

```powershell
git -C "C:\ATK-BOOT\runtime\repository" remote add github "https://github.com/AnNguyenHoai/Antechkid_CenterManager_DB_MonthlyV1.git"
git -C "C:\ATK-BOOT\runtime\repository" push -u github main
```

Use Git Credential Manager / interactive auth. **Never put a PAT/token in command arguments, clone URLs, the repository or this document.** Verify all 3 authoritative files exist on the new PRIVATE GitHub `main`: `database/center.db`, `database/center.db.identity.json`, `manifest.json`. Do NOT delete the offline signed bootstrap workspace: it holds the original DPAPI key for destination-bound provisioning and disaster recovery.

To configure the *actual* production Windows EXE in a **separate clean extracted package**, use the existing `Export Provisioning Request → GitProvisioningAdmin.exe → Import Encrypted Bundle` workflow:
- Destination request originates from the target Windows user/profile.
- Authorized installation is `C:\ATK-BOOT` (has the new, valid shared `runtime/Config/database_key.dpapi`), not the old official CenterManager installation.
- Repository URL must be the NEW PRIVATE monthly V1 database repo, branch `main`, and a dedicated fine-grained PAT scoped only to that repo.
- The v2 workstation bundle encrypts *both* the Git credential and the matching SQLCipher workspace key to the destination. Never copy another Windows user's DPAPI key file.
- Test startup (verified signed MAIN), login, WRITE acquire, Finish Editing, physical restart, backup + restore, Income, Tuition Detail, and second-client concurrency before any live transactions.

## Stop / rollback conditions
- Any failed Windows full CI shard, failed artifact identity check, missing SQLCipher identity, wrong Git URL, long-path handoff, duplicate session month, historical Income in initial bootstrap, or finance mismatch = **STOP**.
- Don't modify SQLCipher keys, bypass permissions, force-delete lock/queue branches or manually reset signed history.
- Old `Antechkid_CenterManager_DatabaseOfficial` remains untouched and available for read-only historical lookup. The new DB starts with **zero historical business records**; legal/accounting opening balances require a separately reconciled business decision. Never treat an empty DB as proof old debts/receipts ceased to exist.
- For Windows files, keep short root paths (`C:\ATK-RELEASE`, `C:\ATK-BOOT`, `C:\ATK-APP`) and retain backup/restore evidence.

Related: Production Acceptance issue #623; PR #625; existing `CenterManager/scripts/prepare_sec06_isolated_uat.py` and `CenterManager/scripts/initialize_production_database.py`.
