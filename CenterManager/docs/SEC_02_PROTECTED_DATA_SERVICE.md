# SEC-02 Protected Data Service

## Goal

Prevent an employee Windows account from directly reading, deleting or replacing the production database, SQLCipher key bundle or managed backups while preserving authorized CenterManager access through a dedicated Windows service identity.

## Threat boundary

SQLCipher + user-scope DPAPI protect copied/offline artifacts, but they do not isolate secrets from another process running under the same employee Windows token. NTFS ACLs also cannot distinguish CenterManager.exe from Explorer/PowerShell when both run as the same user.

SEC-02 therefore uses a separate identity:

```text
Employee Windows User
        |
        | local authenticated named pipe
        v
CenterManager desktop
        |
        v
AnTechKidsData Windows service
NT SERVICE\AnTechKidsData
        |
        +-- machine-DPAPI SQLCipher key bundle
        +-- center.db
        +-- encrypted backups
        +-- protected metadata
```

## Phase A — merged

- `ProtectedStorageMode`: `transitional` / `enforced`.
- `%ProgramData%\AnTechKids\CenterManager\Protected` service-owned layout.
- `AnTechKidsData` Windows service identity.
- dry-run-by-default ACL script.
- protocol v1 safe-operation contract.
- enforced mode rejects GUI-local SQLCipher/key access.

## Phase B1 — broker/key/storage migration

### Local authenticated named pipe

`\\.\pipe\AnTechKidsData.v1` is created with:

- `PIPE_REJECT_REMOTE_CLIENTS`;
- Windows ACL requiring an authenticated local identity;
- server-side client impersonation to obtain the caller SID/account;
- 64 KiB bounded JSON request/response messages;
- protocol version and request correlation checks.

The server logs request id, operation and trusted Windows caller identity. It does not log request payloads or key material.

### Operation-oriented protocol

Allowed v1 operations remain:

- `health`
- `validate_database`
- `create_backup`

There is no raw SQL API and no raw-key API. This is intentional: a generic SQL tunnel would let another process under the employee token bypass application authorization with arbitrary `DELETE`, `DROP` or mutation commands.

Restore/reset/rekey remain excluded until SEC-04 adds an administrator authorization envelope at the service boundary.

### Service-owned key

The legacy key is currently user-DPAPI protected. Phase B1 introduces machine-scoped DPAPI only for the protected service key bundle. The bundle is then protected by NTFS ACL so only:

- `NT SERVICE\AnTechKidsData`
- `SYSTEM`
- local `Administrators`

can read it.

Machine DPAPI is not considered sufficient without this ACL. A process that can read a machine-scoped DPAPI blob on the same host may be able to unprotect it.

`provision_protected_service_key.py` re-wraps the existing workspace key without printing or logging its raw value.

### Protected staging

`stage_protected_database.py`:

1. validates the encrypted runtime DB;
2. proves the legacy and protected key bundles resolve to the same workspace key;
3. copies ciphertext to protected storage;
4. fsyncs and validates the temporary copy;
5. atomically publishes protected `center.db`;
6. stages runtime metadata;
7. leaves the existing runtime DB unchanged.

This makes rollback possible before final cutover.

### Protected backup

Service `create_backup`:

- unseals the key only inside the Windows service process;
- validates protected `center.db`;
- creates a SQLCipher logical snapshot;
- includes protected metadata;
- fsyncs and validates the encrypted snapshot;
- removes partial backup directories on failure.

## Phase B1 deployment verification

Before ACL enforcement, from elevated PowerShell:

```powershell
python .\scripts\provision_protected_service_key.py
python .\scripts\stage_protected_database.py
.\scripts\install_protected_data_service.ps1 -Start
python .\scripts\verify_protected_data_service.py
```

Optional backup verification:

```powershell
python .\scripts\verify_protected_data_service.py --backup
```

Only after service verification should ACL preparation be evaluated:

```powershell
.\scripts\prepare_protected_storage_acl.ps1
```

That command remains dry-run unless `-Apply` is explicitly supplied.

## Why `enforced` is still not production-ready

The application repositories still consume local SQLAlchemy `Session` objects. Therefore normal CRUD persistence still occurs in the desktop process in transitional mode. Phase B1 moves key ownership, protected artifact validation and backup behind the service, but it does **not** yet move all domain persistence behind the broker.

Consequently:

```text
ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced
        +
GUI attempts create_production_engine()/inspect_runtime_database()
        => ProtectedStorageConfigurationError
```

There is no fallback to the employee-owned SQLCipher key path.

## Phase B2 required before final SEC-02 enforcement

1. Migrate production domain persistence from GUI-local SQLAlchemy sessions to operation-oriented service APIs.
2. Keep authorization checks in the trusted service boundary; do not introduce a generic SQL tunnel.
3. Move authoritative Git materialization/publish DB operations into the service boundary.
4. Run a maintenance cutover so protected DB/metadata are staged from a quiescent final runtime state.
5. Apply service-only ACLs.
6. Set `ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced`.
7. Prove on a real employee Windows token that direct read/delete/replace of DB/key/backups fails while CenterManager workflows succeed.
8. Run restart, crash, backup, publish and recovery UAT.

## Security invariant

Production release must never claim SEC-02 complete while the employee desktop process can load the raw workspace key or directly open `center.db`.
