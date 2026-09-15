# EMPLOYEE 1.1 Save Logging & Form UX Fix

## Problems fixed

### 1. Employee save failures were not written to the application log

The employee form caught exceptions and only showed a small warning popup. The root cause was therefore difficult to diagnose.

The form now logs the full exception and traceback with:

```python
logger.exception("Failed to save employee profile...")
```

The user-facing dialog shows the immediate reason while the full technical traceback is available in `runtime/Logs/centermanager.log`.

### 2. Employee dialog was too small

The employee profile dialog now uses a larger minimum size and resize target:

- Minimum: `760 x 580`
- Default: `820 x 650`

The form is organized into:

- Basic Information
- Employment Information

The address field is now multiline for easier input.

## Verification

- `python -m compileall -q src` passes.
