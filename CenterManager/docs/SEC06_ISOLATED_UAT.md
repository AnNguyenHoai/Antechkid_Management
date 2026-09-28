# SEC-06 Isolated Windows Production UAT

Use this workflow for destructive/manual SEC-06 checks without touching the real production data repository.

## Safety contract

`prepare_sec06_isolated_uat.py`:

- requires Windows because the production key bundle uses DPAPI;
- requires an extracted package containing `CenterManager.exe`;
- requires NEW target and local-remote paths;
- refuses targets inside the CenterManager source tree;
- copies the release package instead of modifying it;
- removes inherited Database, Config, and repository state only from the copied target;
- creates a fresh SQLCipher runtime DB and DPAPI key;
- migrates and seeds the fresh DB;
- publishes DB + signed SEC-05 identity to an isolated working repository;
- creates `manifest.json` with `runtime_version=1`;
- creates a local bare Git remote and configures the copied package to use its `file://` URL.

The fixture therefore cannot publish UAT data to the configured production GitHub data repository.

## Prepare

From the CenterManager source checkout on Windows:

```powershell
python scripts/prepare_sec06_isolated_uat.py `
  --package "D:\path\to\extracted-release" `
  --target "D:\SEC06-UAT\package" `
  --remote "D:\SEC06-UAT\authoritative.git"
```

Review the dry-run output, then apply:

```powershell
python scripts/prepare_sec06_isolated_uat.py `
  --package "D:\path\to\extracted-release" `
  --target "D:\SEC06-UAT\package" `
  --remote "D:\SEC06-UAT\authoritative.git" `
  --apply --confirm PREPARE-ISOLATED-SEC06-UAT
```

Both target paths must not already exist.

## SEC06-09

Launch `D:\SEC06-UAT\package\CenterManager.exe` and log in with the documented bootstrap admin credential.

PASS criteria:

1. authentication succeeds;
2. normal workspace access is blocked until password change completes;
3. password-change UI appears immediately;
4. after a successful password change, normal workspace access is allowed;
5. restart and login with the new password does not force another password change.

Do not record the bootstrap or replacement password in UAT evidence.

## Reuse

After SEC06-09 is captured, the same disposable environment can be copied/reset for SEC06-10 through SEC06-17. Destructive cases should operate on disposable copies rather than on the production repository or its DPAPI bundle.
