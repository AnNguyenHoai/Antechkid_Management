from pathlib import Path


def test_uat_documentation_forbids_recording_passwords():
    docs = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "SEC06_ISOLATED_UAT.md"
    ).read_text(encoding="utf-8")

    assert "Do not record the bootstrap or replacement password in UAT evidence." in docs
    assert "normal workspace access is blocked until password change completes" in docs
