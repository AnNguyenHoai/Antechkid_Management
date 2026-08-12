# Runtime Architecture - CenterManager

## Purpose

This document describes the Platform Runtime architecture introduced in RC2.

## Runtime Context

`RuntimeContext` is the single execution context of the Platform.

It contains:

- RuntimeManifest
- RuntimeState
- RuntimeConfiguration
- RuntimeSession
- RuntimeVersion

## Runtime States

| State | Description |
|-------|-------------|
| BOOTSTRAP | Application starting |
| INITIALIZING | Initializing components |
| CHECK_REPOSITORY | Checking repository existence |
| VALIDATING | Validating runtime |
| READY | Platform ready |
| OFFLINE | Offline mode |
| ERROR | Error state |

## Bootstrap Sequence
Application
↓
BootstrapManager
↓
RuntimeContextManager.create_context()
↓
RuntimeState: BOOTSTRAP
↓
RuntimeState: INITIALIZING
↓
RuntimeState: CHECK_REPOSITORY
↓
RuntimeState: VALIDATING
↓
RuntimeState: READY

text

## Runtime Manifest

`manifest.json` is the single source of truth for runtime description.

**Fields:**
- `schema_version`: Manifest schema version
- `runtime_version`: Current runtime version
- `database_version`: Database schema version
- `minimum_app_version`: Minimum compatible app version
- `publisher`: Publisher name
- `branch`: Git branch
- `created_at`: Creation timestamp
- `published_at`: Publication timestamp

## Runtime Version

Tracks version information:
- `current`: Current runtime version
- `desired`: Desired version (from remote)
- `last_pull`: Last pull timestamp
- `last_publish`: Last publish timestamp

## Runtime Session

Represents user session:
- `session_id`: Unique session identifier
- `user_id`: User identifier
- `username`: Display name
- `role`: User role
- `machine_id`: Machine identifier
- `mode`: READ or WRITE
- `last_heartbeat`: Heartbeat timestamp

## Runtime Configuration

Platform configuration:
- `deployment_profile`: standalone, collaborative, server
- `app_version`: Application version
- `app_name`: Application name
- `heartbeat_interval`: Heartbeat interval in seconds
- `lock_timeout`: Lock timeout in seconds
- `sync_policy`: Synchronization policy

## Dependency Rule

Platform components receive `RuntimeContext` instead of multiple Runtime objects.

Business Layer NEVER receives RuntimeContext.