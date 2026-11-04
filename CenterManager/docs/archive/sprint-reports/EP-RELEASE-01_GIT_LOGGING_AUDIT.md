# EP-RELEASE-01 Git Logging Audit

## Scope
Audit Git-related runtime logging and startup lifecycle after PR #231.

## Findings
- Git command arguments were logged verbatim; clone arguments can contain credential-bearing URLs and local repository paths.
- Git subprocess stderr was logged verbatim and then propagated through exceptions, so remote URLs, local paths, and credential material could reach logs and tracebacks.
- Git synchronization provider logged repository paths and configured remotes directly.
- Git origin reconciliation logged current/configured remote URLs directly.
- The logging formatter redacted credentials but did not redact local Git paths or repository metadata.
- Startup started background threads before all business services had been constructed, so a startup exception could leave a QThread alive.
- StudentNoteService was made backward-compatible by PR #231, but the application composition root still did not explicitly provide the RepositoryProvider.

## Release contract
1. Git credentials, credential-bearing URLs, raw Git stderr, local repository paths, and runtime filesystem paths must not be written to normal application logs.
2. Git failures must retain a safe error category/message for the user and diagnostics without exposing raw subprocess output.
3. Background synchronization threads start only after application service construction succeeds.
4. The composition root owns the RepositoryProvider dependency for services that require it.
5. Startup failures must perform best-effort background-service cleanup before returning.

## Credential incident hygiene
If a credential has appeared in a log, revoke/rotate it immediately and remove the exposed artifact from shared/distributed locations. This document intentionally contains no credential values or repository paths.
