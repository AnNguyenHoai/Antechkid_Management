#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the CenterManager Windows production release candidate."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import PyInstaller.__main__

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
APP_NAME = "CenterManager"
ADMIN_TOOL_NAME = "GitProvisioningAdmin"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def read_release_version() -> str:
    if not VERSION_FILE.exists():
        raise FileNotFoundError(f"Canonical VERSION file not found: {VERSION_FILE}")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"Invalid CenterManager release version: {version!r}")
    return version


VERSION = read_release_version()
RELEASE_NAME = f"{APP_NAME}-v{VERSION}-windows-x64"
DIST_ROOT = PROJECT_ROOT / "dist"
BUILD_ROOT = PROJECT_ROOT / "build"
RELEASE_ROOT = PROJECT_ROOT / "release"
PACKAGE_ROOT = RELEASE_ROOT / RELEASE_NAME

PORTABLE_GIT_VERSION = "2.54.0"
PORTABLE_GIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.54.0.windows.1/MinGit-2.54.0-64-bit.zip"
PORTABLE_GIT_SHA256 = "04f937e1f0918b17b9be6f2294cb2bb66e96e1d9832d1c298e2de088a1d0e668"

# A release is a clean template. Machine/user-bound secret material must never
# be copied from the build workstation into a destination package.
RUNTIME_EXCLUDES = shutil.ignore_patterns(
    "*.db", "*.db-journal", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3",
    "logs", "Logs", "cache", "Cache", "temp", "Temp", "backup", "Backup",
    "repository", ".git", "__pycache__", "attachments", "Attachments", "Attachment",
    "*.log", "*.tmp", "*.bak", "*.pyc", ".DS_Store", "Thumbs.db",
    "*.dpapi", "git_provisioning_private.json", "config.json",
)


def _remove_tree(path: Path) -> None:
    def _on_rm_error(func, target, exc_info):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            raise
    shutil.rmtree(path, onerror=_on_rm_error)


def clean_outputs() -> None:
    for path in (DIST_ROOT, BUILD_ROOT, RELEASE_ROOT):
        if path.exists():
            try:
                _remove_tree(path)
            except PermissionError as exc:
                raise PermissionError(
                    f"Cannot clean release output '{path}'. Close CenterManager.exe, Git clients, terminals, or other processes using files under this directory, then run build_release.py again."
                ) from exc


def copy_runtime_template() -> None:
    src_runtime = PROJECT_ROOT / "runtime"
    dst_runtime = PACKAGE_ROOT / "runtime"
    if not src_runtime.exists():
        raise FileNotFoundError(f"Runtime template not found: {src_runtime}")
    shutil.copytree(src_runtime, dst_runtime, ignore=RUNTIME_EXCLUDES)
    for dir_name in ("Database", "Export", "Attachment", "Config", "Backup", "Logs", "Reports", "Temp", "metadata", "collaboration", "snapshots"):
        (dst_runtime / dir_name).mkdir(parents=True, exist_ok=True)


def copy_migration_assets() -> None:
    for name in ("alembic.ini", "migrations"):
        source = PROJECT_ROOT / name
        target = PACKAGE_ROOT / name
        if not source.exists():
            raise FileNotFoundError(f"Required migration asset not found: {source}")
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, target)


def bundle_portable_git() -> None:
    target = PACKAGE_ROOT / "git"
    if target.exists():
        _remove_tree(target)
    with tempfile.TemporaryDirectory(prefix="centermanager-mingit-") as tmp:
        archive = Path(tmp) / "MinGit.zip"
        urllib.request.urlretrieve(PORTABLE_GIT_URL, archive)
        digest = hashlib.sha256()
        with archive.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_sha256 = digest.hexdigest()
        if actual_sha256.lower() != PORTABLE_GIT_SHA256.lower():
            raise RuntimeError(f"Portable Git checksum mismatch: expected {PORTABLE_GIT_SHA256}, got {actual_sha256}")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
    git_executable = target / "cmd" / "git.exe"
    if not git_executable.exists():
        raise FileNotFoundError(f"Bundled MinGit {PORTABLE_GIT_VERSION} is missing {git_executable}")


def _numeric_windows_version(version: str) -> tuple[int, int, int, int]:
    match = SEMVER_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"Invalid CenterManager release version: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), 0


def generate_windows_version_metadata() -> Path:
    major, minor, patch, build = _numeric_windows_version(VERSION)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    metadata_path = BUILD_ROOT / "version_metadata.generated.txt"
    metadata_path.write_text(
        "# UTF-8\nVSVersionInfo(\n  ffi=FixedFileInfo(\n"
        f"    filevers=({major}, {minor}, {patch}, {build}),\n    prodvers=({major}, {minor}, {patch}, {build}),\n"
        "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)\n  ),\n  kids=[\n"
        "    StringFileInfo([StringTable(u'040904B0', [\n      StringStruct(u'CompanyName', u'AN TECHKIDS'),\n"
        "      StringStruct(u'FileDescription', u'CenterManager Desktop Application'),\n"
        f"      StringStruct(u'FileVersion', u'{major}.{minor}.{patch}.{build}'),\n"
        "      StringStruct(u'InternalName', u'CenterManager'),\n      StringStruct(u'LegalCopyright', u'Copyright (c) 2026 AN TECHKIDS'),\n"
        "      StringStruct(u'OriginalFilename', u'CenterManager.exe'),\n      StringStruct(u'ProductName', u'CenterManager'),\n"
        f"      StringStruct(u'ProductVersion', u'{VERSION}')\n    ])]),\n    VarFileInfo([VarStruct(u'Translation', [0x0409, 0x04B0])])\n  ]\n)\n",
        encoding="utf-8",
    )
    return metadata_path


def generate_windows_app_icon() -> Path:
    """Materialize the embedded AN TECHKIDS logo for PyInstaller."""
    import ast
    import base64

    source = PROJECT_ROOT / "src" / "centermanager" / "branding" / "app_logo.py"
    module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    encoded_logo = None
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if isinstance(target, ast.Name) and target.id == "APP_LOGO_PNG_BASE64":
            encoded_logo = ast.literal_eval(node.value)
            break
    if not isinstance(encoded_logo, str):
        raise RuntimeError("APP_LOGO_PNG_BASE64 was not found in branding/app_logo.py")

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    png_path = BUILD_ROOT / "app_logo.generated.png"
    png_path.write_bytes(base64.b64decode(encoded_logo))
    return png_path


def resolve_source_commit() -> str:
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", github_sha):
        return github_sha.lower()
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    sha = result.stdout.strip()
    if result.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return sha.lower()
    raise RuntimeError("Could not resolve the source Git commit for release provenance.")


def release_channel() -> str:
    return "release-candidate" if "-rc" in VERSION else "production"


def write_release_manifest(source_commit: str) -> Path:
    manifest_path = PACKAGE_ROOT / "RELEASE_MANIFEST.json"
    manifest = {
        "application": APP_NAME, "version": VERSION, "release_channel": release_channel(),
        "source_commit": source_commit, "platform": "windows-x64",
        "portable_git_version": PORTABLE_GIT_VERSION, "admin_provisioning_tool": f"AdminTools/{ADMIN_TOOL_NAME}.exe",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def write_release_readme(source_commit: str) -> None:
    (PACKAGE_ROOT / "README_RELEASE.md").write_text(
        f"# CenterManager {VERSION}\n\nWindows {release_channel()} build.\n\nSource commit: `{source_commit}`\n\n"
        "## Start\n\nRun CenterManager.exe. Mutable application data is stored in the runtime folder beside the executable.\n\n"
        "## Secure workstation provisioning\n\n"
        f"This package bundles Git for Windows MinGit {PORTABLE_GIT_VERSION}; no system Git installation is required.\n\n"
        "A clean destination exports a provisioning request. Run `AdminTools/GitProvisioningAdmin.exe` only from an already-authorized CenterManager installation that can open the production database. The admin tool combines the Git credential with that installation's existing shared workspace database key, encrypts both for the destination request, and never creates a replacement database key. Import the returned bundle on the destination; both secrets are then re-wrapped with destination-local Windows DPAPI.\n\n"
        "## Important\n\n- Do not delete or rename the runtime or git folders.\n"
        "- Release packages intentionally contain no config.json, DPAPI bundle, or provisioning private identity from the build machine.\n"
        "- Keep AdminTools/GitProvisioningAdmin.exe under administrator control; it is not needed for normal destination operation.\n"
        "- When Git synchronization is configured, the Git repository database is authoritative and startup refuses to use a stale local database if synchronization fails.\n"
        "- Never generate a new database key for an existing authoritative encrypted database.\n"
        "- Use the application's backup flow for test data.\n- Alembic migration assets are shipped with the release and are required for startup.\n"
        "- Verify the distributed ZIP against its `.sha256` file before installation.\n- If startup fails, inspect error.log beside the executable and runtime/Logs/.\n",
        encoding="utf-8",
    )


def write_uat_checklist() -> None:
    (PACKAGE_ROOT / "UAT_CHECKLIST.md").write_text(
        f"# CenterManager {VERSION} Production Candidate UAT Checklist\n\n"
        "- [ ] Verify RELEASE_MANIFEST.json version and source commit match the approved release.\n"
        "- [ ] Verify the release ZIP against the distributed SHA-256 checksum.\n"
        "- [ ] Confirm the release contains no runtime/Config/config.json, *.dpapi, or git_provisioning_private.json from the build machine.\n"
        "- [ ] Verify AdminTools/GitProvisioningAdmin.exe is present and launches without Python installed.\n"
        "- [ ] On a clean destination, export CenterManager_Workstation_Provisioning_Request.json.\n"
        "- [ ] On an already-authorized administrator PC, create a destination-bound workstation bundle.\n"
        "- [ ] Import the bundle and confirm both Git synchronization and encrypted database startup succeed.\n"
        "- [ ] Restart the destination and confirm provisioning is not requested again.\n"
        "- [ ] Confirm a bundle created for one destination is rejected by another destination.\n"
        "- [ ] Confirm a copied foreign-DPAPI database_key.dpapi triggers provisioning and is replaced only after authenticated bundle import.\n"
        "- [ ] Launch CenterManager.exe from a clean Windows user directory.\n- [ ] Login succeeds with the test account.\n"
        "- [ ] Student workspace and navigation work.\n- [ ] Class and Teacher workspaces open.\n"
        "- [ ] Session / Attendance / Assessment flows open.\n- [ ] Finance workspace opens.\n- [ ] Student Timeline opens.\n"
        "- [ ] Export/report actions produce expected files.\n- [ ] Backup/restore can be exercised with test data.\n"
        "- [ ] Restarting the executable preserves expected runtime data.\n- [ ] No source checkout or Python installation is required to launch either executable.\n"
        "- [ ] Git synchronization works without a system Git installation.\n- [ ] With Git configured, startup uses the repository database rather than a stale local database.\n"
        "- [ ] If the authoritative repository database is unavailable, startup refuses to continue with a stale local database.\n"
        "- [ ] A write/publish from one machine is visible after startup on a second machine.\n",
        encoding="utf-8",
    )


def _pyinstaller_hidden_imports() -> list[str]:
    return [
        "centermanager", "centermanager.core", "centermanager.database", "centermanager.models",
        "centermanager.repositories", "centermanager.services", "centermanager.ui", "centermanager.export",
        "centermanager.platform", "centermanager.events", "alembic", "sqlalchemy", "openpyxl", "reportlab",
        "bcrypt", "git", "PySide6", "cryptography", "logging.config",
    ]


def build_executable() -> Path:
    version_metadata = generate_windows_version_metadata()
    app_icon = generate_windows_app_icon()
    args = ["run.py", "--name", APP_NAME, "--onefile", "--windowed", "--paths", str(PROJECT_ROOT / "src"),
            "--version-file", str(version_metadata), "--icon", str(app_icon),
            "--add-data", f"{PROJECT_ROOT / 'alembic.ini'}{os.pathsep}.",
            "--add-data", f"{PROJECT_ROOT / 'migrations'}{os.pathsep}migrations"]
    for module in _pyinstaller_hidden_imports():
        args.extend(["--hidden-import", module])
    PyInstaller.__main__.run(args)
    executable = DIST_ROOT / f"{APP_NAME}.exe"
    if not executable.exists():
        raise FileNotFoundError(f"PyInstaller did not create {executable}")
    return executable


def build_admin_provisioning_executable() -> Path:
    """Build the standalone, windowed administrator provisioning utility."""
    args = [
        "git_provisioning_admin.py", "--name", ADMIN_TOOL_NAME, "--onefile", "--windowed",
        "--paths", str(PROJECT_ROOT / "src"), "--hidden-import", "centermanager.services.git_provisioning",
        "--hidden-import", "centermanager.database.encryption", "--hidden-import", "centermanager.core.secret_store",
        "--hidden-import", "cryptography", "--hidden-import", "PySide6",
    ]
    PyInstaller.__main__.run(args)
    executable = DIST_ROOT / f"{ADMIN_TOOL_NAME}.exe"
    if not executable.exists():
        raise FileNotFoundError(f"PyInstaller did not create {executable}")
    return executable


def write_archive_checksum(archive: Path) -> Path:
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="ascii")
    return checksum_path


def create_release_package(executable: Path, admin_executable: Path, source_commit: str) -> tuple[Path, Path]:
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, PACKAGE_ROOT / executable.name)
    admin_dir = PACKAGE_ROOT / "AdminTools"
    admin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(admin_executable, admin_dir / admin_executable.name)
    copy_runtime_template()
    copy_migration_assets()
    bundle_portable_git()
    write_release_manifest(source_commit)
    write_release_readme(source_commit)
    write_uat_checklist()
    archive = Path(shutil.make_archive(str(RELEASE_ROOT / RELEASE_NAME), "zip", root_dir=RELEASE_ROOT, base_dir=RELEASE_NAME))
    checksum = write_archive_checksum(archive)
    return archive, checksum


def main() -> None:
    clean_outputs()
    source_commit = resolve_source_commit()
    print(f"Building {APP_NAME} {VERSION} from {source_commit}...")
    executable = build_executable()
    admin_executable = build_admin_provisioning_executable()
    archive, checksum = create_release_package(executable, admin_executable, source_commit)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"Release package: {archive}")
    print(f"Release checksum: {checksum}")
    print(f"ZIP size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
