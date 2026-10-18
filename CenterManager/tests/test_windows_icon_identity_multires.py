# -*- coding: utf-8 -*-
"""Regression coverage for stable Windows application icon identity."""
from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


def _load_build_release():
    spec = importlib.util.spec_from_file_location(
        "centermanager_build_release_icon_test",
        ROOT / "build_release.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generated_windows_ico_contains_all_canonical_resolutions(tmp_path):
    build_release = _load_build_release()
    build_release.BUILD_ROOT = tmp_path

    icon_path = build_release.generate_windows_icon()
    raw = icon_path.read_bytes()

    reserved, icon_type, count = struct.unpack_from("<HHH", raw, 0)
    assert reserved == 0
    assert icon_type == 1
    assert count == len(build_release.APPLICATION_ICON_SIZES)

    sizes = []
    for index in range(count):
        offset = 6 + index * 16
        width, height = struct.unpack_from("<BB", raw, offset)
        sizes.append((256 if width == 0 else width, 256 if height == 0 else height))

    expected = [(size, size) for size in build_release.APPLICATION_ICON_SIZES]
    assert sizes == expected
    assert expected == [
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    ]


def test_runtime_and_release_share_one_canonical_icon_asset():
    runtime = (SRC / "ui" / "application_icon.py").read_text(encoding="utf-8")
    release = (ROOT / "build_release.py").read_text(encoding="utf-8")
    entry = (ROOT / "run.py").read_text(encoding="utf-8")

    assert "centermanager.core.application_icon_asset" in runtime
    assert "centermanager.core.application_icon_asset" in release
    assert "_APP_LOGO_PNG" not in entry
    assert "BrandedApplication" not in entry
    assert "app_module.QApplication" not in entry


def test_windows_app_identity_is_configured_before_qapplication_creation():
    app = (SRC / "app.py").read_text(encoding="utf-8")
    identity = (SRC / "core" / "application_identity.py").read_text(encoding="utf-8")

    assert 'WINDOWS_APP_USER_MODEL_ID = "AnTechKids.CenterManager"' in identity
    assert "SetCurrentProcessExplicitAppUserModelID" in identity
    assert "configure_windows_app_identity()" in app
    assert app.index("configure_windows_app_identity()") < app.index(
        "qapp = QApplication(sys.argv)"
    )


def test_release_build_passes_generated_multires_icon_to_pyinstaller():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")

    assert "windows_icon = generate_windows_icon()" in source
    assert '"--icon", str(windows_icon)' in source
    assert "_ico_dib_frame" in source
