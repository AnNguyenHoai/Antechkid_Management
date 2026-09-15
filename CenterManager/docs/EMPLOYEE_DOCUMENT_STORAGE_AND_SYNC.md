# Employee Document Storage & Cross-Machine Sync

## Canonical storage

Employee documents are stored as local runtime files, not as database BLOBs:

```text
runtime/
└── Attachments/
    └── Employees/
        └── <EMPLOYEE_CODE>/
            └── <DOCUMENT_TYPE>/
                └── <UUID>_<ORIGINAL_FILENAME>
```

The database stores only metadata and a runtime-relative path, for example:

```text
Attachments/Employees/EMP-00001/CV/abc123_cv.pdf
```

## Cross-machine source of truth

The collaboration repository mirrors the same files:

```text
runtime/
└── repository/
    └── Attachments/
        └── Employees/
            └── <EMPLOYEE_CODE>/
                └── <DOCUMENT_TYPE>/
                    └── <UUID>_<ORIGINAL_FILENAME>
```

The Git repository is the cross-machine source of truth.

## Publish lifecycle

Uploading a document copies the source file into the local runtime only.

```text
Upload
  -> runtime/Attachments/Employees/...
  -> DB metadata
  -> Finish Editing / Publish
  -> runtime/repository/Attachments/Employees/...
  -> git commit + push
```

A document is therefore visible on another machine **after the writer finishes/publishes the transaction** and the other machine completes startup/background synchronization.

The document must not be uploaded directly into the Git repository from the UI; the synchronization layer owns that boundary.

## Materialization on another machine

Startup synchronization:

1. Fetches/resets the repository to the authoritative `main`.
2. Copies the repository database into `runtime/Database/center.db`.
3. Mirrors `repository/Attachments/Employees` into `runtime/Attachments/Employees`.
4. The Employee Document Service resolves stored relative paths against the local runtime root.
5. The UI opens the resulting absolute local file.

If the DB record exists but the repository file does not, the document is considered not synchronized/published and cannot be opened on the other machine.

## Security and integrity boundaries

- Stored document paths must be relative to the runtime.
- Resolved paths must remain under `runtime/Attachments`.
- Repository paths must remain under `runtime/repository`.
- Publish mirrors Employee attachments before staging `git add -A`.
- Startup mirrors repository attachments back into the runtime.
- The runtime copy is disposable; the repository copy is authoritative for collaboration.

## Important operational rule

**Do not assume an uploaded document is cross-machine immediately.** The upload is local working state until the current write transaction is successfully published. This is intentional so documents and database changes cross the same collaboration/write-lock boundary.
