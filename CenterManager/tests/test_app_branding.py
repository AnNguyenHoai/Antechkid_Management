from pathlib import Path


def test_launcher_applies_antechkids_window_icon():
    source = (Path(__file__).resolve().parents[1] / "run.py").read_text(encoding="utf-8")
    assert "class BrandedApplication" in source
    assert "setWindowIcon(QIcon(pixmap))" in source
    assert "app_module.QApplication = BrandedApplication" in source
