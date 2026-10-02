# -*- coding: utf-8 -*-
"""GitConfigService - credential-safe Git configuration persistence.

Git transport metadata is portable with the application package, while the
access token is a local secret. On Windows the token is protected with DPAPI
for the current Windows user. Copying a runtime to another machine therefore
keeps repository metadata but intentionally requires one local provisioning
step for the token.

Legacy whole-config ENC:v1/DPAPI:v2 bundles remain readable for migration.
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from centermanager.core.crypto import decrypt_git_config, encrypt_git_config
from centermanager.core.secret_store import protect_secret, unprotect_secret
from centermanager.core.git_locator import locate_git
from centermanager.core.git_url_safety import validate_repository_url
from centermanager.core.paths import get_paths
from centermanager.platform.synchronization._windows_subprocess import hidden_subprocess_kwargs
from centermanager.platform.synchronization.git.git_credential_helper import GitCredentialHelper
from centermanager.platform.synchronization.git_windows_auth import append_http_auth_config

logger = logging.getLogger(__name__)

_SUPPORTED_BUNDLE_PREFIXES = ("ENC:v1:", "DPAPI:v2:")
_LOCAL_SECRET_KEY = "token_secret"
_PORTABLE_REQUIRED_FIELDS = ("repository_url", "username")


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
    allow_local_file_remote: bool = False

    def to_dict(self) -> dict:
        return {
            "repository_url": validate_repository_url(
                self.repository_url,
                allow_local_file_remote=self.allow_local_file_remote,
            ),
            "username": self.username,
            "token": self.token,
            "branch": self.branch,
            "email": self.email,
            "allow_local_file_remote": self.allow_local_file_remote,
        }

    def to_portable_dict(self) -> dict:
        """Return non-secret Git metadata safe to copy between machines."""
        return {
            "repository_url": validate_repository_url(
                self.repository_url,
                allow_local_file_remote=self.allow_local_file_remote,
            ),
            "username": self.username,
            "branch": self.branch,
            "email": self.email,
            "allow_local_file_remote": self.allow_local_file_remote,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GitConfig":
        allow_local_file_remote = bool(data.get("allow_local_file_remote", False))
        return cls(
            repository_url=validate_repository_url(
                data["repository_url"],
                allow_local_file_remote=allow_local_file_remote,
            ),
            username=data["username"],
            token=data["token"],
            branch=data.get("branch", "main"),
            email=data.get("email", ""),
            allow_local_file_remote=allow_local_file_remote,
        )

    @classmethod
    def from_portable_dict(cls, data: dict, token: str = "") -> "GitConfig":
        allow_local_file_remote = bool(data.get("allow_local_file_remote", False))
        return cls(
            repository_url=validate_repository_url(
                data["repository_url"],
                allow_local_file_remote=allow_local_file_remote,
            ),
            username=data.get("username", ""),
            token=token,
            branch=data.get("branch", "main"),
            email=data.get("email", ""),
            allow_local_file_remote=allow_local_file_remote,
        )


class GitConfigService:
    """Persist portable Git metadata plus a locally protected access token."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or get_paths().config_file
        self._config: Optional[GitConfig] = None
        self._encrypted_bundle: Optional[str] = None

    @staticmethod
    def _is_supported_bundle(bundle) -> bool:
        return isinstance(bundle, str) and bundle.startswith(_SUPPORTED_BUNDLE_PREFIXES)

    @staticmethod
    def _has_portable_metadata(section: dict) -> bool:
        return all(
            isinstance(section.get(field), str) and bool(section.get(field).strip())
            for field in _PORTABLE_REQUIRED_FIELDS
        )

    @classmethod
    def _is_split_config(cls, section: dict) -> bool:
        secret = section.get(_LOCAL_SECRET_KEY)
        return cls._has_portable_metadata(section) and isinstance(secret, str) and bool(secret.strip())

    def _read_root(self) -> dict:
        if not self._config_path.exists():
            return {}
        with open(self._config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def _git_section(self) -> dict:
        try:
            section = self._read_root().get("git", {})
            return section if isinstance(section, dict) else {}
        except Exception:
            return {}

    def has_config(self) -> bool:
        """Return whether any Git configuration record exists.

        Portable metadata without a token is still a valid deployment record;
        ``get_config`` remains the authority for whether local credentials are
        usable on the current Windows identity.
        """
        section = self._git_section()
        return self._has_portable_metadata(section) or self._is_supported_bundle(section.get("config"))

    def credential_status(self) -> str:
        """Return a non-secret status suitable for bootstrap diagnostics."""
        section = self._git_section()
        if not section:
            return "not_configured"

        if self._has_portable_metadata(section):
            secret = section.get(_LOCAL_SECRET_KEY)
            if not isinstance(secret, str) or not secret.strip():
                return "not_provisioned_on_this_machine"
            try:
                self._unprotect_local_token(secret)
                return "ready"
            except Exception:
                return "not_provisioned_on_this_machine"

        legacy = section.get("config")
        if self._is_supported_bundle(legacy):
            try:
                decrypt_git_config(legacy)
                return "legacy_ready"
            except Exception:
                return "legacy_not_provisioned_on_this_machine"
        return "invalid"

    def get_portable_config(self) -> Optional[GitConfig]:
        """Load copy-safe metadata without requiring the local token."""
        section = self._git_section()
        if self._has_portable_metadata(section):
            try:
                return GitConfig.from_portable_dict(section)
            except Exception:
                return None

        legacy = section.get("config")
        if self._is_supported_bundle(legacy):
            try:
                decrypted = decrypt_git_config(legacy)
                if isinstance(decrypted, str):
                    decrypted = json.loads(decrypted)
                config = GitConfig.from_dict(decrypted)
                config.token = ""
                return config
            except Exception:
                # Foreign whole-config DPAPI hides metadata as well; old packages
                # cannot recover it without re-entering repository information.
                return None
        return None

    def _write_git_section(self, section: dict) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._read_root() if self._config_path.exists() else {
            "application": {"name": "CenterManager", "version": "0.1.0"}
        }
        data["git"] = section
        with open(self._config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())

    def _protect_local_token(self, token: str) -> str:
        if os.name == "nt":
            return protect_secret(token)
        # Linux/macOS are development/test platforms only.
        return encrypt_git_config({"token": token})

    def _unprotect_local_token(self, bundle: str) -> str:
        if bundle.startswith("DPAPI:v2:"):
            return unprotect_secret(bundle)
        if bundle.startswith("ENC:v1:"):
            payload = decrypt_git_config(bundle)
            if isinstance(payload, dict) and isinstance(payload.get("token"), str):
                return payload["token"]
            raise ValueError("Invalid local Git token payload")
        raise ValueError("Unsupported local Git token format")

    def _persist_split_config(self, config: GitConfig) -> None:
        if not config.token:
            raise GitConfigValidationError("Git access token is required")
        section = config.to_portable_dict()
        section[_LOCAL_SECRET_KEY] = self._protect_local_token(config.token)
        self._write_git_section(section)
        self._config = config
        self._encrypted_bundle = section[_LOCAL_SECRET_KEY]
        logger.info("Git configuration saved with local credential protection")

    def load_config(self) -> Optional[GitConfig]:
        section = self._git_section()
        if not section:
            logger.debug("No Git configuration found")
            return None

        # Preferred schema: metadata remains readable after a cross-machine copy,
        # while the token is locally protected and may intentionally be absent or
        # undecryptable until the destination machine is provisioned.
        if self._has_portable_metadata(section):
            secret = section.get(_LOCAL_SECRET_KEY)
            if not isinstance(secret, str) or not secret.strip():
                logger.info(
                    "Git metadata is available but credential is not provisioned for this Windows user/machine"
                )
                return None
            try:
                token = self._unprotect_local_token(secret)
                self._config = GitConfig.from_portable_dict(section, token=token)
                self._encrypted_bundle = secret
                return self._config
            except ValueError:
                logger.info(
                    "Git credential is not provisioned for this Windows user/machine; portable metadata remains available"
                )
                return None
            except Exception:
                logger.exception("Failed to load local Git credential")
                return None

        # Legacy compatibility: the entire Git config used to be one encrypted
        # bundle. If decryptable locally, migrate it to split storage.
        encrypted = section.get("config")
        if not self._is_supported_bundle(encrypted):
            logger.debug("No supported Git configuration found")
            return None
        try:
            decrypted = decrypt_git_config(encrypted)
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)
            if not isinstance(decrypted, dict):
                logger.error("Decrypted Git configuration has invalid type")
                return None

            self._config = GitConfig.from_dict(decrypted)
            self._encrypted_bundle = encrypted
            if os.name == "nt":
                self._persist_split_config(self._config)
                logger.info("Migrated legacy Git credentials to portable metadata + local DPAPI token")
            return self._config
        except ValueError:
            logger.info(
                "Legacy Git credential cannot be decrypted on this Windows user/machine; local provisioning is required"
            )
            return None
        except Exception:
            logger.exception("Failed to load Git configuration")
            return None

    def get_config(self) -> Optional[GitConfig]:
        return self._config if self._config is not None else self.load_config()

    def save_config(self, config: GitConfig) -> bool:
        """Validate plaintext input and wrap its token on the destination machine."""
        try:
            config.repository_url = validate_repository_url(
                config.repository_url,
                allow_local_file_remote=config.allow_local_file_remote,
            )
            if not config.username:
                raise GitConfigValidationError("Git username is required")
            if not config.token:
                raise GitConfigValidationError("Git access token is required")
            if not self.test_connection(config):
                raise GitConfigValidationError("Connection test failed. Invalid credentials or repository.")
            self._persist_split_config(config)
            return True
        except GitConfigValidationError as exc:
            logger.warning("Git configuration validation failed: %s", exc)
            return False
        except Exception:
            logger.exception("Failed to save Git configuration")
            return False

    def save_encrypted_bundle(self, bundle: str) -> None:
        """Legacy import path; DPAPI is intentionally not portable."""
        bundle = bundle.strip()
        if not self._is_supported_bundle(bundle):
            raise GitConfigValidationError("Unsupported encrypted Git configuration format")
        try:
            decrypted = decrypt_git_config(bundle)
            if isinstance(decrypted, str):
                decrypted = json.loads(decrypted)
            for field in ("repository_url", "username", "token"):
                if field not in decrypted:
                    raise GitConfigValidationError(f"Missing required field: {field}")
            config = GitConfig.from_dict(decrypted)
            if not self.test_connection(config):
                raise GitConfigValidationError("Connection test failed. Invalid credentials or repository.")
            self._persist_split_config(config)
        except GitConfigValidationError:
            raise
        except Exception as exc:
            if bundle.startswith("DPAPI:v2:"):
                raise GitConfigValidationError(
                    "This DPAPI credential belongs to another Windows user/machine. "
                    "Enter the Git token on this machine to provision it locally."
                ) from exc
            raise GitConfigValidationError("Invalid encrypted Git configuration") from exc

    def test_connection(self, config: GitConfig) -> bool:
        git_executable = locate_git()
        if not git_executable:
            logger.warning("Git executable unavailable; connection test failed safely")
            return False

        try:
            safe_url = validate_repository_url(
                config.repository_url,
                allow_local_file_remote=config.allow_local_file_remote,
            )
        except ValueError:
            logger.error("Repository URL violates transport policy")
            return False

        helper = GitCredentialHelper(config.username, config.token)
        env = os.environ.copy()
        if config.token:
            env.update(helper.setup_environment())
        else:
            env["GIT_TERMINAL_PROMPT"] = "0"

        if sys.platform == "win32":
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_CONFIG_COUNT"] = "2"
            env["GIT_CONFIG_KEY_0"] = "credential.helper"
            env["GIT_CONFIG_VALUE_0"] = ""
            env["GIT_CONFIG_KEY_1"] = "core.askpass"
            env["GIT_CONFIG_VALUE_1"] = ""
            append_http_auth_config(env, safe_url, helper.http_auth_header())

        try:
            run_kwargs = {
                "capture_output": True,
                "text": True,
                "env": env,
                "check": False,
            }
            run_kwargs.update(hidden_subprocess_kwargs())
            result = subprocess.run(
                [str(git_executable), "ls-remote", safe_url, "HEAD"],
                **run_kwargs,
            )
            if result.returncode == 0:
                return True
            stderr = (result.stderr or "").lower()
            logger.error(
                "Authentication failed"
                if any(x in stderr for x in ("authentication", "401", "403"))
                else "Git ls-remote failed"
            )
            return False
        except Exception:
            logger.exception("Connection test failed")
            return False
        finally:
            helper.cleanup()

    def validate_bundle(self, bundle: str) -> "ValidationResult":
        """Validate legacy import bundles without treating DPAPI as portable."""
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
            if bundle.startswith("DPAPI:v2:"):
                return ValidationResult(
                    False,
                    "DPAPI credentials are local to the Windows user/machine that created them.",
                )
            return ValidationResult(False, "Encrypted Git configuration is invalid")

    def clear_config(self) -> None:
        if not self._config_path.exists():
            return
        try:
            data = self._read_root()
            data.pop("git", None)
            with open(self._config_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            self._config = None
            self._encrypted_bundle = None
            logger.info("Git configuration cleared")
        except Exception as exc:
            raise GitConfigError("Failed to clear Git configuration") from exc


class ValidationResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message
