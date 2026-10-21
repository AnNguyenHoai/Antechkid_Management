from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"


def test_launcher_delegates_icon_ownership_to_application_bootstrap():
    launcher = (ROOT / "run.py").read_text(encoding="utf-8")
    app = (SRC / "app.py").read_text(encoding="utf-8")

    # run.py must stay a thin launcher. Installing a second QApplication/icon
    # source here previously caused EXE/window/taskbar branding to diverge.
    assert "from centermanager.app import main" in launcher
    assert "class BrandedApplication" not in launcher
    assert "_APP_LOGO_PNG" not in launcher
    assert "app_module.QApplication" not in launcher

    # The canonical runtime icon belongs to the real application bootstrap.
    assert "build_application_icon" in app
    assert "qapp.setWindowIcon(build_application_icon())" in app
