# -*- coding: utf-8 -*-
"""
GitConfigService - Handles encrypted Git configuration.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from centermanager.core.paths import get_paths
from centermanager.core.crypto import encrypt_git_config, decrypt_git_config
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.synchronization.git.git_provider import GitProvider

logger = logging.getLogger(__name__)


class GitConfigError(Exception):
    """Base exception for Git config errors."""
    pass


class GitConfigValidationError(GitConfigError):
    """Raised when validation fails."""
    pass


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
        """Check if encrypted config exists."""
        if not self._config_path.exists():
            return False
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            git_data = data.get("git", {})
            if "config" in git_data:
                bundle = git_data["config"]
                if isinstance(bundle, str) and bundle.startswith("ENC:v1:"):
                    return True
            return False
        except Exception:
            return False

    def load_config(self) -> Optional[GitConfig]:
        """Load and decrypt Git configuration."""
        if not self.has_config():
            logger.debug("No Git configuration found")
            return None

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            encrypted = data.get("git", {}).get("config")

            if not isinstance(encrypted, str):
                logger.error(f"Expected string for git.config, got {type(encrypted).__name__}")
                return None

            if not encrypted.startswith("ENC:v1:"):
                logger.error("git.config is not an encrypted bundle")
                return None

            try:
                decrypted = decrypt_git_config(encrypted)
            except ValueError as e:
                logger.error(f"Decryption failed: {e}")
                # If decryption fails, the config is corrupted - clear it
                self.clear_config()
                return None

            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)

            if not isinstance(decrypted, str):
                logger.error(f"Decrypted result is not a string: {type(decrypted).__name__}")
                return None

            config_data = json.loads(decrypted)
            self._config = GitConfig.from_dict(config_data)
            self._encrypted_bundle = encrypted
            return self._config

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load Git configuration: {e}")
            return None

    def get_config(self) -> Optional[GitConfig]:
        """Get current config (loads if not loaded)."""
        if self._config is None:
            return self.load_config()
        return self._config

    def save_config(self, config: GitConfig) -> bool:
        """
        Save plaintext GitConfig (encrypts and stores).
        Returns True on success, False on failure.
        """
        try:
            plaintext = json.dumps(config.to_dict(), ensure_ascii=False)
            bundle = encrypt_git_config(plaintext)
            self.save_encrypted_bundle(bundle)
            return True
        except Exception as e:
            logger.error(f"Failed to save Git configuration: {e}")
            return False

    def save_encrypted_bundle(self, bundle: str) -> None:
        bundle = bundle.strip()  # Trim khoảng trắng/dòng mới
        if not bundle.startswith("ENC:v1:"):
            raise GitConfigValidationError("Invalid bundle format. Must start with 'ENC:v1:'")

        try:
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)
            config_data = json.loads(decrypted)
            required = ["repository_url", "username", "token"]
            for field in required:
                if field not in config_data:
                    raise GitConfigValidationError(f"Missing required field: {field}")
            config = GitConfig.from_dict(config_data)
            if not self.test_connection(config):
                raise GitConfigValidationError("Connection test failed. Invalid credentials or repository.")
        except json.JSONDecodeError:
            raise GitConfigValidationError("Invalid JSON in decrypted payload.")
        except Exception as e:
            raise GitConfigValidationError(f"Invalid bundle: {str(e)}")

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"application": {"name": "CenterManager", "version": "0.1.0"}}
            data["git"] = {"config": bundle}
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._config = config
            self._encrypted_bundle = bundle
            logger.info("Git configuration saved successfully.")
        except Exception as e:
            raise GitConfigError(f"Failed to save configuration: {str(e)}")

    def test_connection(self, config: GitConfig) -> bool:
        """Test connection to GitHub with given config."""
        try:
            import subprocess
            import os
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            url = config.repository_url
            if config.token:
                if "://" in url:
                    protocol, rest = url.split("://", 1)
                    if "@" in rest:
                        rest = rest.split("@")[-1]
                    auth_url = f"{protocol}://{config.token}@{rest}"
                else:
                    auth_url = url
            else:
                auth_url = url

            cmd = ["git", "ls-remote", auth_url, "HEAD"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False
            )
            if result.returncode == 0:
                return True
            else:
                stderr = result.stderr.lower()
                if "authentication" in stderr or "401" in stderr or "403" in stderr:
                    logger.error("Authentication failed")
                    return False
                else:
                    logger.error(f"Git ls-remote failed: {result.stderr}")
                    return False
        except Exception as e:
            logger.exception("Connection test failed")
            return False

    def validate_bundle(self, bundle: str) -> "ValidationResult":
        bundle = bundle.strip()
        try:
            if not bundle.startswith("ENC:v1:"):
                return ValidationResult(False, "Invalid bundle format. Must start with 'ENC:v1:'")

            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, dict):
                decrypted = json.dumps(decrypted, ensure_ascii=False)
            config_data = json.loads(decrypted)
            required = ["repository_url", "username", "token"]
            for field in required:
                if field not in config_data:
                    return ValidationResult(False, f"Missing required field: {field}")

            config = GitConfig.from_dict(config_data)
            if not self.test_connection(config):
                return ValidationResult(False, "Connection test failed. Invalid credentials or repository.")

            return ValidationResult(True, "Bundle is valid.")
        except json.JSONDecodeError:
            return ValidationResult(False, "Invalid JSON in decrypted payload.")
        except Exception as e:
            return ValidationResult(False, f"Validation error: {str(e)}")

    def clear_config(self) -> None:
        """Clear Git configuration from config file."""
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "git" in data:
                del data["git"]
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._config = None
            self._encrypted_bundle = None
            logger.info("Git configuration cleared.")
        except Exception as e:
            raise GitConfigError(f"Failed to clear configuration: {str(e)}")


class ValidationResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message