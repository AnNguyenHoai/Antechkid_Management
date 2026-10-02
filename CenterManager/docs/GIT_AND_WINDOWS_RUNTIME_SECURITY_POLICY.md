# CenterManager Git and Windows Runtime Security Policy

## Scope

This document defines the P2/P3 pre-SEC06 security contract for repository transport, Windows runtime ownership, installation location, and Git credentials.

## 1. Repository transport

Normal CenterManager repository URLs MUST use credential-free HTTPS:

```text
https://github.com/<owner>/<repository>.git
```

The following are rejected by application policy:

- `http://` repository URLs.
- SSH/SCP-style repository URLs such as `git@github.com:owner/repo.git`.
- HTTPS URLs containing username, password, PAT, token, or any other user-info.
- `file://` repository URLs unless an isolated/manual fixture explicitly opts in through the encrypted Git configuration.

Credentials MUST NOT appear in Git argv, persisted remote URLs, `git remote -v`, application logs, or surfaced Git errors.

### SEC06 isolated UAT exception

SEC06 destructive/manual UAT intentionally uses a local bare Git repository. The fixture generator writes `allow_local_file_remote=true` inside its encrypted Git configuration. This exception is disabled by default and is not written by the normal Git configuration UI.

The exception exists only to keep the isolated UAT repository local and prevent accidental publication to the production data repository.

## 2. Windows runtime ownership

CenterManager uses this operational ownership rule:

> One Windows user account owns one CenterManager installation/runtime tree.

A runtime tree MUST NOT be shared between Windows accounts. Two users must not point separate CenterManager processes at the same runtime folder, database, DPAPI-protected credential bundle, or Git working tree.

This hardening does **not** relocate `get_paths().runtime_root`. Existing runtime-path semantics remain unchanged to avoid changing the release manifest, bootstrap, DPAPI, backup/recovery, or SEC06 contracts during this gate.

## 3. Writable installation directory

Because the packaged application maintains `runtime/` relative to its installation/package tree, the extracted/installed CenterManager directory MUST be writable by the Windows user who owns that runtime.

Recommended per-user location:

```text
%LOCALAPPDATA%\AnTechKids\CenterManager\
    CenterManager.exe
    runtime\
```

An equivalent user-owned writable directory is acceptable. Do not install the current package into a shared or administrator-owned directory such as `C:\Program Files\...` while keeping the runtime beside the executable.

Do not grant broad Everyone/Users write permissions to a shared installation as a workaround. Use a separate per-user installation/runtime tree instead.

## 4. Dedicated Git service credential

Production CenterManager Git authentication MUST use a dedicated repository service credential, not a developer/employee personal PAT.

The existing encrypted configuration field is still named `token` for schema/backward compatibility, but its required operational meaning is now **CenterManager service credential**.

Minimum credential policy:

- Dedicated identity used only by CenterManager.
- Scoped only to the authoritative CenterManager data repository.
- Repository contents: read/write only as required by synchronization.
- Repository metadata: read.
- No organization administration, repository administration, workflow administration, or unrelated repository access.
- Defined owner and rotation/revocation procedure.

Migration sequence:

1. Create the dedicated service identity/credential.
2. Grant only the minimum repository permissions above.
3. Configure CenterManager with the credential through the normal encrypted configuration flow.
4. Validate clone/fetch/pull/push and collaboration lock operations.
5. Revoke the old personal PAT only after the service credential has passed validation.

Do not paste the credential into a repository URL or Git command line.

## 5. Credential injection boundary

CenterManager authentication is process-local:

- Windows GUI builds inject the HTTPS Authorization header through `GIT_CONFIG_*` environment entries for the child `git.exe` process and disable host credential helpers/AskPass.
- Non-Windows development/test flows use the secret-free AskPass helper; the helper script reads the service credential from the child environment and contains no secret itself.
- Repository URLs remain credential-free in both cases.

The process-local secret environment key is `CENTERMANAGER_GIT_SERVICE_CREDENTIAL`.

## 6. Legacy token-in-URL path

Token-bearing clone URLs are deprecated and prohibited. Code must not construct forms such as:

```text
https://<token>@github.com/owner/repo.git
```

Any old configuration containing embedded URL credentials must be rejected and replaced with a clean HTTPS URL plus the separately encrypted service credential.

## 7. Pre-SEC06 acceptance gate

Before SEC06-13 continues, verify all of the following:

- Production repository configuration accepts credential-free HTTPS and rejects HTTP/SSH/user-info URLs.
- `file://` is rejected by default and accepted only with the encrypted isolated-UAT opt-in.
- No Git clone/fetch/pull/push path puts the credential in argv or the remote URL.
- The SEC06 isolated fixture still uses its local bare repository successfully.
- Installation/runtime ownership follows one Windows user ↔ one writable installation/runtime tree.
- The production credential is a dedicated service credential rather than a personal PAT.
- Focused regression tests and repository CI are green.

Only after this gate should SEC06 resume at SEC06-13; earlier completed SEC06 steps are not restarted.
