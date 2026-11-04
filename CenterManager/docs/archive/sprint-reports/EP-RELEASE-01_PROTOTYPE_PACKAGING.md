# EP-RELEASE-01 — Prototype Packaging & Release

## Scope

Create a repeatable Windows packaging path for the current CenterManager prototype without changing business behavior.

## Packaging contract

- Entry point: `run.py`.
- Packaging mode: PyInstaller `--onefile` + `--windowed`.
- Mutable runtime data remains external in `runtime/` beside `CenterManager.exe`.
- Live SQLite databases, SQLite journals/WAL/SHM files, caches, logs, temp files and backups are excluded from the release runtime template.
- The executable must resolve its project/runtime root from the executable directory when frozen.
- Release package contains the executable, external runtime template, release README and UAT checklist.

## Build command

From `CenterManager/` on Windows:

```text
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python build_release.py
```

Expected artifact:

```text
release/
  CenterManager-v0.1.0-prototype-windows-x64/
    CenterManager.exe
    runtime/
    README_RELEASE.md
    UAT_CHECKLIST.md
  CenterManager-v0.1.0-prototype-windows-x64.zip
```

## CI

`.github/workflows/windows-prototype-release.yml` builds on Windows, runs the packaging contracts, verifies the executable/package structure, and uploads the ZIP as a workflow artifact. It runs manually or for tags matching `v*-prototype`.

## Release gate

The workflow proves that packaging succeeds; it does not prove full desktop behavior on a real user machine. Before distributing the prototype to users, run the included UAT checklist from a clean Windows user directory and record any production defect as a separate fix task with a regression test.

## Explicit non-goals

- No installer/auto-updater.
- No production signing/notarization.
- No public release publishing.
- No database migration redesign.
- No UI redesign.
- No new business features.
