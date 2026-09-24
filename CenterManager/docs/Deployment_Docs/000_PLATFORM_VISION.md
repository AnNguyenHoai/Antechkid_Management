# CenterManager Collaboration Platform — Vision

Version: 1.1  
Status: **APPROVED VISION**  
Updated: 2026-09-24

## 1. Purpose

This document describes the long-term platform direction of CenterManager. It is a vision document, not a literal implementation specification.

Current implementation architecture is documented in `docs/ARCHITECTURE.md`. Approved domain specifications remain authoritative for their domain. GitHub Issues define task scope. This vision must guide evolution but does not override a more specific approved contract merely because it is higher-level.

## 2. Background

CenterManager evolved from a standalone desktop management application into a multi-workspace operational system used by different roles such as teachers, reception/administration, finance and managers.

The current product remains a desktop application, but now includes a collaboration platform, controlled write ownership, synchronization, authorization and runtime-version concepts.

## 3. Product vision

CenterManager is a **workspace-based education-center operations platform** that can support lightweight standalone use and controlled collaborative deployment without forcing a heavy server stack.

The platform should provide:

- shared operational data;
- controlled editing/write ownership;
- synchronization/version history;
- authorization and auditability;
- deployment flexibility;
- deterministic behavior suitable for small/medium education centers.

## 4. Current collaboration model

The current implemented collaboration direction is deterministic rather than real-time multi-writer editing.

When Git-backed collaboration is configured:

- startup synchronization participates in the authoritative runtime-data lifecycle;
- edit/write ownership is coordinated by Platform collaboration services;
- synchronization/version behavior is owned by Platform infrastructure;
- business domains do not run Git directly.

When collaboration is not configured, the application can operate in a true local/offline mode with a local runtime database.

## 5. Design philosophy

### Business/domain first

Business rules should have stable owners and should not be rewritten merely because deployment technology changes.

### Platform-owned collaboration

Synchronization, runtime context, edit/write coordination and version infrastructure belong to the Platform layer rather than individual Student/Class/Finance modules.

### Explicit boundaries

UI projects state, services own application/domain orchestration, repositories own persistence mechanics, and Platform owns cross-cutting collaboration/deployment concerns.

### Incremental evolution

CenterManager should evolve from the current desktop/collaboration architecture toward other deployment models only when product needs justify the complexity.

### Deterministic collaboration

The product intentionally favors controlled editing and predictable consistency over CRDT/OT-style concurrent document editing.

## 6. Technology independence — practical interpretation

Business semantics should not depend on Git, network-provider details or UI framework behavior.

This does **not** mean all business code is abstracted from SQLite/SQLAlchemy at every level. The current architecture uses repositories as the persistence boundary and SQLAlchemy/SQLite as infrastructure behind that boundary.

Avoid speculative abstraction purely to satisfy a theoretical future backend.

## 7. Core principles

1. One business concept has one authoritative domain owner.
2. UI does not own persistence or canonical business rules.
3. Collaboration/synchronization belongs to Platform.
4. WRITE ownership does not replace fine-grained authorization.
5. Infrastructure is replaceable where an explicit boundary exists or a task justifies one.
6. Historical/accounting meaning must not be silently rewritten by migration or UI convenience.
7. Architecture evolves through reviewed contracts, not undocumented shortcuts.
8. Deterministic behavior is preferred over maximum concurrency.
9. Documentation must distinguish current implementation from future vision.

## 8. Product boundaries

CenterManager is optimized for education-center operations.

It is not intended to become:

- Google Docs/Notion-style collaborative document editing;
- a general distributed database;
- a real-time CRDT collaboration platform;
- a universal ERP for unrelated industries.

## 9. Current non-goals

Unless a future product decision changes them, the platform does not target:

- simultaneous conflict-free editing of the same business record by many writers;
- OT/CRDT document collaboration;
- automatic semantic merge of conflicting business transactions;
- mandatory cloud/server infrastructure for every deployment.

## 10. Success criteria

The platform direction is successful when:

- workspace/domain behavior remains coherent as infrastructure evolves;
- new features reuse existing service/repository/platform boundaries;
- synchronization can evolve without duplicating Git logic in business modules;
- deployments remain manageable for the center's operational scale;
- agents/developers can implement tasks from approved specs + Issues + repository contracts;
- documentation reflects reality instead of preserving obsolete architecture diagrams.

## 11. Evolution direction

Possible future evolution includes:

```text
Current collaborative desktop
        ↓
stronger deployment profiles / operational tooling
        ↓
optional LAN/server/hybrid backends where justified
        ↓
future enterprise integrations
```

This is directional, not a committed release roadmap.

Do not build unused server/storage abstractions solely because a later generation is imaginable.

## 12. Relationship with other specifications

Current document roles:

- `000_PLATFORM_VISION.md` — long-term direction;
- `100_ARCHITECTURE_PRINCIPLES.md` — durable architecture rules;
- `200_COLLABORATIVE_ARCHITECTURE.md` — implemented collaboration/platform shape and direction;
- `300_WORKSPACE_MODEL.md` — workspace ownership model;
- `400_EDIT_SESSION_PROTOCOL.md` and related protocol docs — collaboration protocol details;
- `docs/ARCHITECTURE.md` — current implementation architecture;
- domain specs — authoritative domain contracts;
- root `AGENTS.md` — coding-agent workflow;
- GitHub Issues — task implementation contracts.

No high-level vision statement should be used to override a specific approved domain invariant without an explicit architecture/product decision.

## Final statement

CenterManager is a desktop-first education-center operations platform with a growing collaboration/platform layer.

Its architecture should preserve business/domain clarity while allowing deployment and infrastructure to evolve only as real product needs require.