# Tuition Engine V1 — UAT activation (draft SQLCipher database ONLY)

**Release state: TEST MODE.** This guide does **not** authorize production activation. Git MAIN is authoritative and the normal app remains in legacy tuition mode. This branch introduces no automatic migration or mass conversion.

## Prerequisites
1. Build a new Windows EXE from the commit containing the UAT activation gate; a previously built EXE will not expose the new controls.
2. Use an **isolated disposable Windows runtime** with an independent Git remote / clone and a copy of the SQLCipher DB. Never point the UAT runtime at the production Git collaboration repository. Do not run concurrent production WRITE clients on this test repository.
3. Ensure the runtime SQLCipher key, app log-in, WRITE authority and required `class.update` / `tuition.enrollment.override` privileges exist. Migration must run via the existing authorized startup gate.
4. Do not create a new version of a previously activated production monthly plan.

## Start the UAT application
In the **same PowerShell process** used to launch the copied test EXE:

```powershell
$env:ANTECHKIDS_TUITION_V1_UAT = "1"
& "C:\UAT\CenterManager\CenterManager.exe"  # replace with your UAT EXE path
```

The gate accepts **exactly** `1`. A normal app launch, missing environment variable, or value `true` keeps the controls hidden. No database or policy change occurs merely by enabling this mode. Close the UAT app and unset the variable (`Remove-Item Env:ANTECHKIDS_TUITION_V1_UAT`) to return to the default UI.

## Manual UAT workflow
1. Sign in, Start Editing, and open the desired **Class → Học phí tháng**. Enter `UAT` in the explicit confirmation box to acknowledge the disposable database.
2. Select the **first day of a future month**. Set monthly amount; preview the original Session IDs/dates and sum. Save Draft then activate plan. The price allocation becomes immutable.
3. Choose **Chuyển học sinh (UAT)** inside the same dialog. Select **one active Enrollment** and a future first-of-month date. Click **Tạo backup SQLCipher**. This creates an actual managed snapshot; plaintext backups cannot authorize activation.
4. Confirm the opt-in for that one student. The business service independently verifies backup freshness/integrity (under 1 hour), valid WRITE permission, canonical Enrollment, tuition history reconciliation, unattributed receipts and activated plan. A failure stops the conversion and displays the exact reason. An Enrollment already switched cannot be activated again.
5. Open Income → Tuition for this Enrollment. Select monthly / quarterly quote, review amount, and post exactly **one genuine Income**. Inspect Tuition Detail, Wallet/Outstanding, class cancellation/makeup and Finish Editing.
6. End WRITE normally and restart the test EXE. Confirm original-month tuition and prepaid balances persist across Git MAIN sync/recovery.

## Important constraints
- `ANTECHKIDS_TUITION_V1_UAT=1` unlocks test controls, **not** the underlying preflight.
- The existing Enrollment pricing form still creates legacy tuition snapshots; UAT opt-in is intentionally a separate explicit step.
- A monthly plan is attached to a class; the policy applies only to Enrollments individually opted in.
- Do not treat a successful Windows pytest run as proof of encrypted SQLCipher restore, cross-device Git WRITE race safety or correctness of the test release package.
- Record results against [Production Acceptance #623](https://github.com/AnNguyenHoai/Antechkid_Management/issues/623). A production switch requires a separate reviewed PR after successful physical UAT.

## Rollback
If UAT fails, stop the UAT EXE, do not publish its database to production Git MAIN, and restore/rebuild the isolated UAT runtime from the independently verified snapshot. Never delete historical Enrollment, Income or Tuition outcome data to undo a failed test.
