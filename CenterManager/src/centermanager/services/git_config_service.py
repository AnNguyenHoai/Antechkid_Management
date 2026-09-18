# -*- coding: utf-8 -*-
"""GitConfigService - Handles encrypted Git configuration."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from centermanager.core.crypto import decrypt_git_config, encrypt_git_config
from centermanager.core.git_locator import locate_git
from centermanager.core.paths import get_paths
from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper

logger = logging.getLogger(__name__)


class GitConfigError(Exception):
    """Base exception for Git config errors."""


class GitConfigValidationError(GitConfigError):
    """Raised when validation fails."""


@dataclass
class GitConfig:
    """Plaintext Git configuration."""

    repository_url: str
    username: str
    token: str
    branch: str = "main"
    email: str = ""

    def to_dict(self) -> dict:
        return {
            "repository_url": self.repository_url,
            "username": self.username,
            "token": self.token,
            "branch": self.branch,
            "email": self.email,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GitConfig":
        return cls(
            repository_url=data["repository_url"],
            username=data["username"],
            token=data["token"],
            branch=data.get("branch", "main"),
            email=data.get("email", ""),
        )


class GitConfigService:
    """Service for managing encrypted Git configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or get_paths().config_file
        self._config: Optional[GitConfig] = None
        self._encrypted_bundle: Optional[str] = None

    def has_config(self) -> bool:
        if not self._config_path.exists():
            return False
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            bundle = data.get("git", {}).get("config")
            return isinstance(bundle, str) and bundle.startswith("ENC:v1:")
        except Exception:
            return False

    def load_config(self) -> Optional[GitConfig]:
        if not self.has_config():
            logger.debug("No Git configuration found")
            return None
        try:
            with open(self._config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            encrypted = data.get("git", {}).get("config")
            if not isinstance(encrypted, str) or not encrypted.startswith("ENC:v1:"):
                logger.error("git.config is not a valid encrypted bundle")
                return None
            try:
                decrypted = decrypt_git_config(encrypted)
            except ValueError as exc:
                logger.error("Decryption failed: %s", exc)
                self.clear_config()
                return None
            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)
            if not isinstance(decrypted, str):
                logger.error("Decrypted Git configuration has invalid type")
                return None
            self._config = GitConfig.from_dict(json.loads(decrypted))
            self._encrypted_bundle = encrypted
            return self._config
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON: %s", exc)
            return None
        except Exception as exc:
            logger.error("Failed to load Git configuration: %s", exc)
            return None

    def get_config(self) -> Optional[GitConfig]:
        return self._config if self._config is not None else self.load_config()

    def save_config(self, config: GitConfig) -> bool:
        try:
            plaintext = json.dumps(config.to_dict(), ensure_ascii=False)
            self.save_encrypted_bundle(encrypt_git_config(plaintext))
            return True
        except Exception as exc:
            logger.error("Failed to save Git configuration: %s", exc)
            return False

    def save_encrypted_bundle(self, bundle: str) -> None:
        bundle = bundle.strip()
        if not bundle.startswith("ENC:v1:"):
            raise GitConfigValidationError("Invalid bundle format. Must start with 'ENC:v1:'")
        try:
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)
            config_data = json.loads(decrypted)
            for field in ("repository_url", "username", "token"):
                if field not in config_data:
                    raise GitConfigValidationError(f"Missing required field: {field}")
            config = GitConfig.from_dict(config_data)
            if not self.test_connection(config):
                raise GitConfigValidationError("Connection test failed. Invalid credentials or repository.")
        except json.JSONDecodeError as exc:
            raise GitConfigValidationError("Invalid JSON in decrypted payload.") from exc
        except GitConfigValidationError:
            raise
        except Exception as exc:
            raise GitConfigValidationError(f"Invalid bundle: {str(exc)}") from exc

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            else:
                data = {"application": {"name": "CenterManager", "version": "0.1.0"}}
            data["git"] = {"config": bundle}
            with open(self._config_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            self._config = config
            self._encrypted_bundle = bundle
            logger.info("Git configuration saved successfully.")
        except Exception as exc:
            raise GitConfigError(f"Failed to save configuration: {str(exc)}") from exc

    def test_connection(self, config: GitConfig) -> bool:
        """Test Git access without putting the token in process arguments."""
        git_executable = locate_git()
        if not git_executable:
            logger.warning("Git executable unavailable; connection test failed safely.")
            return False

        helper = GitCredentialHelper(config.username, config.token)
        env = os.environ.copy()
        if config.token:
            env.update(helper.setup_environment())
        else:
            env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            cmd = [str(git_executable), "ls-remote", config.repository_url, "HEAD"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.returncode == 0:
                return True
            stderr = result.stderr.lower()
            if "authentication" in stderr or "401" in stderr or "403" in stderr:
                logger.error("Authentication failed")
            else:
                logger.error("Git ls-remote failed")
            return False
        except Exception:
            logger.exception("Connection test failed")
            return False
        finally:
            helper.cleanup()

    def validate_bundle(self, bundle: str) -> "ValidationResult":
        bundle = bundle.strip()
        try:
            if not bundle.startswith("ENC:v1:"):
                return ValidationResult(False, "Invalid bundle format. Must start with 'ENC:v1:'")
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)
            config_data = json.loads(decrypted)
            for field in ("repository_url", "username", "token"):
                if field not in config_data:
                    return ValidationResult(False, f"Missing required field: {field}")
            config = GitConfig.from_dict(config_data)
            if not self.test_connection(config):
                return ValidationResult(False, "Connection test failed. Invalid credentials or repository.")
            return ValidationResult(True, "Bundle is valid.")
        except json.JSONDecodeError:
            return ValidationResult(False, "Invalid JSON in decrypted payload.")
        except Exception as exc:
            return ValidationResult(False, f"Validation error: {str(exc)}")

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
            logger.info("Git configuration cleared.")
        except Exception as exc:
            raise GitConfigError(f"Failed to clear configuration: {str(exc)}") from exc


class ValidationResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message
