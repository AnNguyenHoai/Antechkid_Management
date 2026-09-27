# SEC-02 Protected Data Service

## Goal

Prevent an employee Windows account from directly reading, deleting or replacing the production database, SQLCipher key bundle or managed backups while preserving authorized CenterManager access through a dedicated Windows service identity.

## Threat boundary

SQLCipher + user-scope DPAPI protect copied/offline artifacts, but they do not isolate secrets from another process running under the same employee Windows token. NTFS ACLs also cannot distinguish CenterManager.exe from Explorer/PowerShell when both run as the same user.

SEC-02 therefore requires a separate identity:

```text
Employee Windows User
        |
        | authenticated IPC
        v
CenterManager desktop
        |
        v
AnTechKidsData Windows service
NT SERVICE\AnTechKidsData
        |
        +-- SQLCipher key
        +-- center.db
        +-- encrypted backups
        +-- protected metadata
```

## Phase A implemented in this branch

1. `ProtectedStorageMode`
   - default: `transitional`
   - opt-in: `ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced`
   - enforced mode rejects all direct production DB access from the desktop process.

2. Protected service-owned layout
   - `%ProgramData%\AnTechKids\CenterManager\Protected\Database`
   - `%ProgramData%\AnTechKids\CenterManager\Protected\Key`
   - `%ProgramData%\AnTechKids\CenterManager\Protected\Backup`
   - `%ProgramData%\AnTechKids\CenterManager\Protected\metadata`

3. Windows service identity host
   - service: `AnTechKidsData`
   - virtual account / service SID: `NT SERVICE\AnTechKidsData`
   - service host currently owns lifecycle/identity only; the DB broker is intentionally not enabled yet.

4. ACL preparation
   - dry-run by default;
   - refuses to apply unless the Windows service exists;
   - removes inherited ACLs;
   - grants Full Control only to the service SID, SYSTEM and local Administrators;
   - grants no access to Users or Authenticated Users.

5. IPC protocol v1 contract
   - health
   - validate_database
   - create_backup
   - no raw-key operation exists;
   - restore/reset/rekey are intentionally deferred to SEC-04 authorization work.

## Why enforced mode currently fails closed

The application repositories still consume local SQLAlchemy `Session` objects. Therefore CenterManager desktop still needs direct database access in transitional mode. Applying service-only ACLs before replacing that Session boundary with a broker-backed adapter would simply break the application.

The code explicitly rejects this unsafe mixed state:

```text
ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced
        +
GUI attempts create_production_engine()/inspect_runtime_database()
        => ProtectedStorageConfigurationError
```

There is no fallback to the employee-owned SQLCipher key path.

## Deployment commands for Phase A testing

Run from an elevated PowerShell in the CenterManager environment:

```powershell
.\scripts\install_protected_data_service.ps1 -Start
.\scripts\prepare_protected_storage_acl.ps1
```

The ACL command above is a dry run. Do not use `-Apply` until Phase B database brokering has passed Windows UAT.

## Phase B required before production enforcement

1. Implement authenticated named-pipe broker in the service.
2. Move SQLCipher key provisioning/unsealing into the service account.
3. Replace GUI-local production SQLAlchemy engine/session creation with a broker-backed persistence boundary.
4. Move runtime DB, authoritative materialization and backups into protected storage.
5. Prove employee token cannot read/delete/replace protected artifacts.
6. Apply ACLs and set `ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced`.
7. Run real-machine restart, crash, backup, publish and recovery UAT.

## Security invariant

Production release must never claim SEC-02 complete while the employee desktop process can load the raw workspace key or directly open `center.db`.
