# EP-ARCH-03 — Runtime Context Normalization

## Objective

Make `RuntimeContext` a single platform type and remove the duplicate runtime-context implementation that currently exists under two package paths.

## Audit Finding

The codebase contains two concrete `RuntimeContext` classes:

- `centermanager.platform.context.runtime_context.RuntimeContext`
- `centermanager.platform.runtime.context.runtime_context.RuntimeContext`

`PlatformContext` imports the first type, while `RuntimeContextManager` imports the second. The two classes do not have the same fields or behavior: the runtime-owned type also carries `session`, `configuration`, `correlation_id`, and `can_write()`.

This creates a latent type/contract split even though current tests and manual flows pass.

## Contract

The runtime-owned `RuntimeContext` is the single concrete implementation.

The historical public import path remains supported as a compatibility re-export:

```text
centermanager.platform.context.runtime_context.RuntimeContext
        ↓
centermanager.platform.runtime.context.runtime_context.RuntimeContext
```

No second implementation may be introduced.

## Compatibility

`RuntimeContext()` remains constructible without an explicit `context_id`; the canonical implementation generates one automatically. This preserves `PlatformContext.create_default()` behavior.

## Validation

Regression tests must prove:

1. Both public/import paths resolve to the same class object.
2. `PlatformContext.create_default()` contains the canonical runtime context.
3. `RuntimeContextManager.create_context()` returns the same canonical type.
