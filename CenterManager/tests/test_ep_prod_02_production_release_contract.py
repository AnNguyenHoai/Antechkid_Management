from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT.parent / ".github" / "workflows" / "windows-prototype-release.yml"
BUILDER = ROOT / "build_release.py"
VERSION_FILE = ROOT / "VERSION"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_prod_02_uses_one_canonical_semver_version_source():
    version = _read(VERSION_FILE).strip()
    builder = _read(BUILDER)
    assert version == "1.0.0-rc1"
    assert 'VERSION_FILE = PROJECT_ROOT / "VERSION"' in builder
    assert "SEMVER_RE" in builder
    assert "VERSION = read_release_version()" in builder
    assert 'VERSION = "0.1.0-prototype"' not in builder
    assert not (ROOT / "version_metadata.txt").exists()


def test_prod_02_generates_windows_metadata_from_canonical_version():
    builder = _read(BUILDER)
    assert "def generate_windows_version_metadata" in builder
    assert 'BUILD_ROOT / "version_metadata.generated.txt"' in builder
    assert 'StringStruct(u\'ProductVersion\', u\'{VERSION}\')' in builder
    assert '"--version-file", str(version_metadata)' in builder


def test_prod_02_package_contains_release_provenance():
    builder = _read(BUILDER)
    for token in (
        '"RELEASE_MANIFEST.json"',
        '"version": VERSION',
        '"source_commit": source_commit',
        '"release_channel": release_channel()',
        '"platform": "windows-x64"',
        'resolve_source_commit()',
    ):
        assert token in builder


def test_prod_02_release_archive_has_sha256_sidecar():
    builder = _read(BUILDER)
    assert "def write_archive_checksum" in builder
    assert "hashlib.sha256()" in builder
    assert 'archive.with_suffix(archive.suffix + ".sha256")' in builder
    assert "write_archive_checksum(archive)" in builder


def test_prod_02_workflow_is_dynamic_and_release_identity_is_gated():
    workflow = _read(WORKFLOW)
    assert "name: Windows Production Release" in workflow
    assert '- "v*"' in workflow
    assert "Get-Content VERSION" in workflow
    assert 'Release tag $env:GITHUB_REF_NAME does not match canonical VERSION' in workflow
    assert "Production release tag must point to current main_repos HEAD" in workflow
    assert 'Manual production release must run from main_repos' in workflow
    assert "0.1.0-prototype-windows-x64" not in workflow


def test_prod_02_workflow_verifies_manifest_and_checksum_before_upload():
    workflow = _read(WORKFLOW)
    assert "RELEASE_MANIFEST.json" in workflow
    assert "Manifest version mismatch" in workflow
    assert "Manifest commit mismatch" in workflow
    assert "Get-FileHash -Algorithm SHA256" in workflow
    assert "Release ZIP checksum mismatch" in workflow
    assert "Upload production release artifact" in workflow
    assert '.zip.sha256' in workflow


def test_prod_02_preserves_existing_clean_machine_release_gate():
    workflow = _read(WORKFLOW)
    builder = _read(BUILDER)
    assert "Run full test suite" in workflow
    assert "Clean-machine portable smoke test" in workflow
    assert "CENTERMANAGER_PORTABLE_SMOKE" in workflow
    assert '"python.exe", "pythonw.exe"' in workflow
    assert "\\src\\" in workflow
    assert "\\.git\\" in workflow
    assert 'PORTABLE_GIT_VERSION = "2.54.0"' in builder
    assert "PORTABLE_GIT_SHA256" in builder
