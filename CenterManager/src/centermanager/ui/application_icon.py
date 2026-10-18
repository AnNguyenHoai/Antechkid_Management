# -*- coding: utf-8 -*-
"""Canonical runtime icon for the AnTechKids desktop application."""
from __future__ import annotations

from PySide6.QtGui import QIcon, QImage, QPixmap

from centermanager.core.application_icon_asset import (
    APPLICATION_ICON_SIZES,
    render_application_icon_rgba,
)


def _pixmap_for_size(size: int) -> QPixmap:
    rgba = render_application_icon_rgba(size)
    image = QImage(
        rgba,
        size,
        size,
        size * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()
    return QPixmap.fromImage(image)


def build_application_icon() -> QIcon:
    """Return one multi-resolution QIcon built from the canonical artwork."""
    icon = QIcon()
    for size in APPLICATION_ICON_SIZES:
        icon.addPixmap(_pixmap_for_size(size))
    return icon


__all__ = ["build_application_icon"]
