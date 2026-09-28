from pathlib import Path


def test_uat_docs_require_disposable_copies_for_destructive_cases():
    docs = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "SEC06_ISOLATED_UAT.md"
    ).read_text(encoding="utf-8")

    assert "Destructive cases should operate on disposable copies" in docs
    assert "production repository" in docs
