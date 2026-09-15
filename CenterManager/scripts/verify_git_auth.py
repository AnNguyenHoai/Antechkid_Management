#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual verification script for Git non-interactive authentication.

Run this script after configuration to verify push/fetch/pull works without credential prompt.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_path))

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config
from centermanager.platform.synchronization import GitSynchronizationProvider


def main():
    print("=" * 60)
    print("Git Authentication Manual Verification")
    print("=" * 60)

    # Load configuration
    config = get_config()
    git_config = config.raw.get("git", {})
    repo_url = git_config.get("repository_url")
    token = git_config.get("token")
    username = git_config.get("username", "CenterManager")

    if not repo_url or not token:
        print("❌ Git configuration incomplete. Please configure repository_url and token.")
        return 1

    print(f"Repository: {repo_url}")
    print(f"User: {username}")
    print(f"Token: {'*' * 8}")

    # Create provider
    repo_path = get_paths().runtime_root / "repository"
    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=repo_url,
        token=token,
        username=username,
        branch="main"
    )

    # Test 1: Connect
    print("\n1. Connecting to repository...")
    if not provider.connect():
        print("❌ Connect failed")
        return 1
    print("✅ Connect successful")

    # Test 2: Fetch
    print("\n2. Testing fetch...")
    try:
        provider.fetch()
        print("✅ Fetch successful")
    except Exception as e:
        print(f"❌ Fetch failed: {e}")
        return 1

    # Test 3: Remote manifest
    print("\n3. Testing remote manifest...")
    try:
        manifest = provider.remote_manifest()
        if manifest:
            print(f"✅ Remote manifest version: {manifest.get('runtime_version', 0)}")
        else:
            print("⚠️ Remote manifest not found (may be empty repository)")
    except Exception as e:
        print(f"❌ Remote manifest failed: {e}")
        return 1

    # Test 4: Pull
    print("\n4. Testing pull...")
    try:
        provider.pull()
        print("✅ Pull successful")
    except Exception as e:
        print(f"❌ Pull failed: {e}")
        return 1

    # Test 5: Push (only if there are changes)
    print("\n5. Testing push (if changes exist)...")
    try:
        # Update manifest version to test push
        current = provider.current_version()
        new_version = current + 1
        provider.update_manifest(new_version)

        result = provider.publish("Verification push from script", username)
        if result:
            print(f"✅ Push successful (version {new_version})")
        else:
            print("ℹ️ No changes to push (or push returned False)")
    except Exception as e:
        print(f"❌ Push failed: {e}")
        return 1

    print("\n" + "=" * 60)
    print("✅ All Git operations completed without credential prompt.")
    print("Non-interactive authentication is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())