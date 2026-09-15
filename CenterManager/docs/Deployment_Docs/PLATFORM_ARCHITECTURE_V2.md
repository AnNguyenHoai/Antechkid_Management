# Platform Architecture V2

## Contexts
PlatformContext
├── RuntimeContext (Data Holder)
├── DeploymentContext
├── SessionContext
├── WorkspaceContext
├── UserContext
└── ConfigurationContext

text

## Lifecycle
CREATED → INITIALIZED → READY → RUNNING → STOPPING → STOPPED

text

## Bootstrap Boundary

BootstrapManager ends at `READY`.

Application Layer handles login, authentication, session creation, and UI.

## Module Registration

Workspaces register via `WorkspaceDescriptor`.

Platform owns workspace lifecycle.

## Synchronization Boundary

Synchronization is persistence-agnostic.
Uses `PersistenceProvider` interface.