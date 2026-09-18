# -*- coding: utf-8 -*-
"""GitConfigService - credential-safe Git configuration persistence."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from centermanager.core.crypto import decrypt_git_config, encrypt_git_config
from centermanager.core.git_locator import locate_git
from centermanager.core.git_url_safety import sanitize_repository_url
from centermanager.core.paths import get_paths
from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper

logger = logging.getLogger(__name__)
_SUPPORTED_BUNDLE_PREFIXES = ("ENC:v1:", "DPAPI:v2:")


class GitConfigError(Exception):
    pass


class GitConfigValidationError(GitConfigError):
    pass


@dataclass
class GitConfig:
    repository_url: str
    username: str
    token: str
    branch: str = "main"
    email: str = ""

    def to_dict(self) -> dict:
        return {
            "repository_url": sanitize_repository_url(self.repository_url),
            "username": self.username,
            "token": self.token,
            "branch": self.branch,
            "email": self.email,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GitConfig":
        return cls(
            repository_url=sanitize_repository_url(data["repository_url"]),
            username=data["username"],
            token=data["token"],
            branch=data.get("branch", "main"),
            email=data.get("email", ""),
        )


class GitConfigService:
    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or get_paths().config_file
        self._config: Optional[GitConfig] = None
        self._encrypted_bundle: Optional[str] = None

    @staticmethod
    def _is_supported_bundle(bundle) -> bool:
        return isinstance(bundle, str) and bundle.startswith(_SUPPORTED_BUNDLE_PREFIXES)

    def has_config(self) -> bool:
        if not self._config_path.exists():
            return False
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return self._is_supported_bundle(data.get("git", {}).get("config"))
        except Exception:
            return False

    def _write_bundle(self, bundle: str) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = {"application": {"name": "CenterManager", "version": "0.1.0"}}
        data["git"] = {"config": bundle}
        with open(self._config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def load_config(self) -> Optional[GitConfig]:
        if not self.has_config():
            logger.debug("No Git configuration found")
            return None
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            encrypted = data.get("git", {}).get("config")
            decrypted = decrypt_git_config(encrypted)
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)
            if not isinstance(decrypted, dict):
                logger.error("Decrypted Git configuration has invalid type")
                return None

            self._config = GitConfig.from_dict(decrypted)
            self._encrypted_bundle = encrypted

            # One-way migration on Windows: once a legacy bundle is successfully
            # read, immediately rewrite it with DPAPI. Never write ENC:v1 again
            # on the production platform.
            if os.name == "nt" and encrypted.startswith("ENC:v1:"):
                migrated = encrypt_git_config(json.dumps(self._config.to_dict(), ensure_ascii=False))
                self._write_bundle(migrated)
                self._encrypted_bundle = migrated
                logger.info("Migrated legacy Git credentials to Windows DPAPI")
            return self._config
        except ValueError:
            logger.error("Git credential decryption failed")
            return None
        except Exception:
            logger.exception("Failed to load Git configuration")
            return None

    def get_config(self) -> Optional[GitConfig]:
        return self._config if self._config is not None else self.load_config()

    def save_config(self, config: GitConfig) -> bool:
        try:
            config.repository_url = sanitize_repository_url(config.repository_url)
            plaintext = json.dumps(config.to_dict(), ensure_ascii=False)
            self.save_encrypted_bundle(encrypt_git_config(plaintext))
            return True
        except Exception:
            logger.exception("Failed to save Git configuration")
            return False

    def save_encrypted_bundle(self, bundle: str) -> None:
        bundle = bundle.strip()
        if not self._is_supported_bundle(bundle):
            raise GitConfigValidationError("Unsupported encrypted Git configuration format")
        try:
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)
            config = GitConfig.from_dict(decrypted)
            for field in ("repository_url", "username", "token"):
                if field not in decrypted:
                    raise GitConfigValidationError(f"Missing required field: {field}")
            if not self.test_connection(config):
                raise GitConfigValidationError("Connection test failed. Invalid credentials or repository.")

            # Re-encrypt through the current platform store so imported legacy
            # bundles never remain persisted on Windows.
            persisted = encrypt_git_config(json.dumps(config.to_dict(), ensure_ascii=False))
            self._write_bundle(persisted)
            self._config = config
            self._encrypted_bundle = persisted
            logger.info("Git configuration saved successfully")
        except GitConfigValidationError:
            raise
        except Exception as exc:
            raise GitConfigValidationError("Invalid encrypted Git configuration") from exc

    def test_connection(self, config: GitConfig) -> bool:
        git_executable = locate_git()
        if not git_executable:
            logger.warning("Git executable unavailable; connection test failed safely")
            return False

        helper = GitCredentialHelper(config.username, config.token)
        env = os.environ.copy()
        if config.token:
            env.update(helper.setup_environment())
        else:
            env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            safe_url = sanitize_repository_url(config.repository_url)
            result = subprocess.run(
                [str(git_executable), "ls-remote", safe_url, "HEAD"],
                capture_output=True, text=True, env=env, check=False,
            )
            if result.returncode == 0:
                return True
            stderr = (result.stderr or "").lower()
            logger.error("Authentication failed" if any(x in stderr for x in ("authentication", "401", "403")) else "Git ls-remote failed")
            return False
        except Exception:
            logger.exception("Connection test failed")
            return False
        finally:
            helper.cleanup()

    def validate_bundle(self, bundle: str) -> "ValidationResult":
        bundle = bundle.strip()
        try:
            if not self._is_supported_bundle(bundle):
                return ValidationResult(False, "Unsupported encrypted Git configuration format")
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)
            for field in ("repository_url", "username", "token"):
                if field not in decrypted:
                    return ValidationResult(False, f"Missing required field: {field}")
            config = GitConfig.from_dict(decrypted)
            if not self.test_connection(config):
                return ValidationResult(False, "Connection test failed. Invalid credentials or repository.")
            return ValidationResult(True, "Bundle is valid.")
        except Exception:
            return ValidationResult(False, "Encrypted Git configuration is invalid or unavailable on this machine")

    def clear_config(self) -> None:
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.pop("git", None)
            with open(self._config_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            self._config = None
            self._encrypted_bundle = None
            logger.info("Git configuration cleared")
        except Exception as exc:
            raise GitConfigError("Failed to clear Git configuration") from exc


class ValidationResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message
