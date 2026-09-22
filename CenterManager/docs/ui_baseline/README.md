# UI visual baseline

This directory documents the source and screenshot baseline introduced by **UI-PROD-00** for revision `df39c7adcd3c896674163fb0ce95dc55abd135f2`.

See [`UI_PROD_00.md`](UI_PROD_00.md) for the capture protocol and acceptance criteria.

## Source inventory

```bash
cd CenterManager
python scripts/ui_inventory.py --write
python scripts/ui_inventory.py --check
```

`UI_INVENTORY.md` and `ui_inventory.json` are generated from every `src/centermanager/ui/**/*.py` file.

## Visual capture

```bash
python scripts/ui_baseline_capture.py
```

After login/navigation, press `Ctrl+Shift+B`.

PNG files and `manifest.json` are runtime evidence and are written under `artifacts/ui-baseline/<revision>/`. They are ignored by Git because captures may contain real center data.
