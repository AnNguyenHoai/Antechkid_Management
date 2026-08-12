# Platform Architecture Freeze v1.0

## Context Model

Platform uses composition of independent contexts:
PlatformContext
├── RuntimeContext (runtime state, manifest, version)
├── DeploymentContext (deployment profile, git config)
├── SessionContext (user session, mode)
├── WorkspaceContext (active workspace, navigation)
├── UserContext (authenticated user, permissions)
└── ConfigurationContext (app config, feature flags)

text

All contexts are independent and data-only.

## PlatformLifecycle

States:
- CREATED
- INITIALIZING
- READY
- RUNNING
- STOPPING
- STOPPED

BootstrapManager brings platform to READY.

## Bootstrap Boundary

BootstrapManager ends at READY.

Login, user session, main window are Application Layer responsibilities.

## Workspace Registration

Modules expose WorkspaceDescriptor.

Platform creates workspaces via factory.

WorkspaceRegistry manages descriptors and instances.

## Synchronization Boundary

SynchronizationProvider is persistence-agnostic.

Works through PersistenceProvider only.