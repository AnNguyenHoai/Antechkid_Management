# Medium / Practical Security Profile

## Goal

CenterManager uses a practical security baseline suitable for a small education center. The goal is to protect production data from common loss/copy mistakes without introducing a service/RPC architecture that would substantially complicate deployment and maintenance.

## Threat model

Protected:
- stolen/lost laptop where the database file is copied;
- opening the production DB with normal SQLite tools;
- copying encrypted backups or the DB to another machine;
- accidental replacement/deletion detected through startup/recovery checks;
- destructive actions performed through the application without authorization.

Not treated as a hard security boundary:
- local Administrator/SYSTEM;
- malware running under the same Windows user;
- a determined employee reverse-engineering the running process to extract the in-memory key;
- binary/app attestation.

## Deployment profiles

`development`
- default when running from Python source (`python run.py`);
- plaintext SQLite test/development databases are allowed;
- existing development Git history does not need to be rewritten;
- SQLCipher can still be forced for UAT with `ANTECHKIDS_FORCE_DATABASE_ENCRYPTION=1`.

`production`
- default when running a frozen/packaged release;
- SQLCipher is mandatory;
- the DB key is a random 256-bit key protected with Windows user-scope DPAPI;
- plaintext authoritative DB artifacts are rejected;
- backups remain encrypted under the existing SEC-03 contract.

Override for controlled testing:

```powershell
$env:ANTECHKIDS_DEPLOYMENT_PROFILE = "production"
```

or

```powershell
$env:ANTECHKIDS_DEPLOYMENT_PROFILE = "development"
```

Invalid profile values fail closed.

## Production first run

Production should start from a fresh blank database rather than migrate the current development/test DB.

Dry run:

```powershell
python .\scripts\initialize_production_database.py
```

Apply on a fresh Windows production workspace:

```powershell
python .\scripts\initialize_production_database.py --apply --confirm CREATE-PRODUCTION-DATABASE
```

The initializer:
1. refuses to overwrite an existing DB or key;
2. forces the production profile;
3. creates a fresh SQLCipher DB and DPAPI-protected key;
4. migrates schema to Alembic head using the keyed SQLCipher connection;
5. seeds roles/permissions/admin;
6. requires the default admin password to be changed on first login;
7. validates the resulting ciphertext and integrity;
8. removes newly-created partial artifacts if setup fails.

Publish only this encrypted DB to the fresh private production data repository. Do not reuse the current development data repository as the production data repository.

## Windows Service / SEC-02 hardening

The `AnTechKidsData` Windows service and named-pipe broker code may remain in the repository as optional future hardening, but they are not required by the medium-security production profile. Do not enable `ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced` for normal production under this model.

## Git history

Plaintext history in the current development repository is accepted because it contains only development/test data and will not become the production data repository. The production data repository must be private and must contain encrypted `database/center.db` from its first production commit.

## Operational rule

For this security profile, recoverability is preferred over attempting to make the DB impossible to delete under the same Windows account. Keep encrypted backup/restore checks, startup integrity checks, admin authorization, and audit records; do not add a mandatory service identity solely to prevent same-user filesystem deletion.
