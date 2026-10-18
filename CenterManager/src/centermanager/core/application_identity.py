# -*- coding: utf-8 -*-
"""Canonical visible product identity for the desktop application.

Internal package/runtime identifiers intentionally remain ``centermanager`` / ``CenterManager``
so existing runtime folders, locks, migrations, and synchronization paths are not renamed.
"""

APPLICATION_DISPLAY_NAME = "AnTechKids - Management App"
APPLICATION_PRODUCT_NAME = "AnTechKids Management App"
APPLICATION_ORGANIZATION = "AnTechKids"
APPLICATION_INTERNAL_NAME = "CenterManager"

WINDOWS_APP_USER_MODEL_ID = "AnTechKids.CenterManager"


def configure_windows_app_identity() -> bool:
    """Set stable Windows taskbar/shell identity before QApplication is created."""
    import sys

    if sys.platform != "win32":
        return False
    try:
        import ctypes

        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        hresult = setter(WINDOWS_APP_USER_MODEL_ID)
        return hresult >= 0
    except Exception:
        return False

