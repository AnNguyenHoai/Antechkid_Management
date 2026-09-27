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
- enforced mode rejects GUI-local SQLCipher/key access.

## Phase B1 — merged

### Local authenticated named pipe

The local service broker rejects remote clients, impersonates the connected Windows pipe token to obtain the caller SID/account, bounds JSON messages, and correlates every request. It does not log request payloads or key material.

### Protected key/storage/backup

- existing workspace key can be re-wrapped for the service using machine-scoped DPAPI;
- NTFS ACL remains the primary local isolation boundary;
- encrypted DB + metadata can be staged non-destructively into ProgramData;
- service-owned backup creates a validated SQLCipher snapshot plus metadata;
- raw key and raw SQL operations do not exist.

## Phase B2 — authenticated application/domain boundary

Protocol v2 uses:

```text
\\.\pipe\AnTechKidsData.v2
```

A Windows SID is **not** sufficient authorization for business operations because another PowerShell/Python process launched by the same employee has the same SID. Domain writes therefore require two independent identities:

1. the caller SID derived by pipe impersonation;
2. an application session issued by the service after canonical CenterManager authentication.

### Service-owned application session

`authenticate` executes inside `AnTechKidsData` using the existing `PermissionService`. This preserves:

- active/locked account checks;
- failed-attempt lockout behavior;
- current and legacy password hash verification;
- legacy password-hash upgrade;
- `last_login` handling;
- canonical password policy.

A successful login creates a cryptographically random service session token. The token:

- remains only in desktop process memory;
- is bound to the authenticated Windows caller SID;
- expires after a bounded lifetime;
- is revoked on logout.

Every authorized domain request re-loads the user and role from the protected DB. Disabling/locking an account or changing its role therefore takes effect without trusting stale role claims from the GUI.

### Operation-oriented domain APIs

The first B2 vertical slice contains:

- `authenticate`
- `logout`
- `user.change_password`
- `student.list`
- `student.create`
- capability-authorized `create_backup`

Student operations call the existing `StudentService`; they do not duplicate repository/domain validation in the broker. DTOs cross IPC, never ORM objects.

There remains no API for:

- raw SQL;
- raw workspace key;
- arbitrary table CRUD;
- restore/reset/rekey.

A generic SQL tunnel is forbidden because any employee process able to call it could bypass CenterManager authorization with arbitrary `DELETE`, `DROP`, or update statements.

### Desktop principal boundary

`ProtectedPermissionServiceAdapter` converts the service-authenticated DTO into a lightweight principal containing only identity, role and capability names. `LoginDialog` and `ChangePasswordDialog` accept principal objects rather than requiring an ORM `User`, so authentication UI can migrate to the service without exposing a database session to the employee process.

## Why `enforced` is still not production-ready

B2 currently establishes the trusted authentication/session/domain API pattern and a student vertical slice. CenterManager startup, Git source-of-truth materialization, schema migration, and many remaining application services still use GUI-local SQLAlchemy sessions.

Therefore:

```text
ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced
        +
GUI attempts create_production_engine()/inspect_runtime_database()
        => ProtectedStorageConfigurationError
```

This fail-closed behavior is intentional. No release may set `enforced` until every required production persistence path has moved behind the service.

## Remaining B2 cutover work

1. Wire service-backed authentication into the composition root after startup dependencies have been migrated in dependency order.
2. Expand operation-oriented APIs across remaining production domains; do not create a generic SQL/ORM proxy.
3. Move startup DB lifecycle/schema migration into the service.
4. Move authoritative Git DB materialization/publish operations into the service boundary.
5. Move remaining backup/restore maintenance entry points behind service authorization.
6. Perform a quiescent final staging/cutover of DB + metadata.
7. Apply service-only ACLs.
8. Set `ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced`.
9. Prove on a real employee Windows token that direct DB/key/backup read/delete/replace fails while approved CenterManager workflows succeed.
10. Run restart, crash, publish, backup and recovery UAT.

## Security invariant

Production release must never claim SEC-02 complete while the employee desktop process can load the raw workspace key, directly open `center.db`, or bypass application authorization through the IPC boundary.
