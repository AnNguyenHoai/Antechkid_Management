# EP-EMP-06-FIX — Capability Contract Regression Cleanup

## Objective

Restore the Employee Workspace capability contract after EP-EMP-06 without weakening authorization.

## Scope

- Restore the canonical `can_view_self` capability property expected by Employee Workspace callers/tests.
- Ensure self-service employee fixtures grant `employee.update.self` where the product contract allows safe self-editing.
- Keep UI capability state and service authorization aligned.
- Do not broaden Manager permissions and do not alter Schedule or Work Registration business rules.

## Validation

Run the targeted Employee capability regression tests first, then the complete test suite:

```text
pytest -q
```

The change must preserve negative authorization tests: `employee.view.self` must never imply `employee.update.self`, and cross-employee operations must still require the corresponding all-scope capability.
