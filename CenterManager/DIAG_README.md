# UI popup diagnostics

`sitecustomize.py` records QMessageBox warning/critical/information calls to `runtime/Logs/ui_popup_diagnostics.log` together with a caller stack. This is diagnostic-only and does not change authorization behavior.
