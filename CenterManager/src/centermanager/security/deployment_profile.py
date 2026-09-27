# -*- coding: utf-8 -*-
"""Deployment profile for the practical/medium security policy.

Source execution defaults to development so local test data can remain plaintext.
Frozen/package execution defaults to production so released builds require
SQLCipher without depending on an operator-managed environment variable.
"""
from __future__ import annotations

import os
import sys
from enum import Enum
from typing import Mapping


_PROFILE_ENV = "ANTECHKIDS_DEPLOYMENT_PROFILE"


class DeploymentProfileError(RuntimeError):
    """Raised when the deployment profile configuration is invalid."""


class DeploymentProfile(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


def deployment_profile(env: Mapping[str, str] | None = None) -> DeploymentProfile:
    values = os.environ if env is None else env
    configured = str(values.get(_PROFILE_ENV, "")).strip().lower()
    if configured:
        try:
            return DeploymentProfile(configured)
        except ValueError as exc:
            raise DeploymentProfileError(
                f"Unsupported {_PROFILE_ENV} value: {configured!r}"
            ) from exc

    return (
        DeploymentProfile.PRODUCTION
        if getattr(sys, "frozen", False)
        else DeploymentProfile.DEVELOPMENT
    )


def is_production_profile(env: Mapping[str, str] | None = None) -> bool:
    return deployment_profile(env) is DeploymentProfile.PRODUCTION
