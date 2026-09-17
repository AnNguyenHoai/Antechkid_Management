# EP-RELEASE-01 Security Logging

## Logging contract

Application console and file log output must not expose Git credentials, credential-bearing remote URLs, or common access-token formats.

Sensitive material is redacted at the formatter boundary so exception messages and tracebacks are sanitized as well as normal log messages.

## Operational rule

Do not commit runtime logs, exported configuration bundles, or files containing Git credentials to the repository.

If a credential is observed in a released or shared log, revoke or rotate it immediately and remove the exposed artifact from all distribution channels.
