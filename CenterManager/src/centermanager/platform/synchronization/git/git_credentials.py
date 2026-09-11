# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional

@dataclass
class GitCredentials:
    repository_url: str
    branch: str
    token: str
    username: str
    email: str

    @classmethod
    def from_config(cls, config: dict) -> Optional["GitCredentials"]:
        git_config = config.get("git", {})
        if not git_config:
            return None
        return cls(
            repository_url=git_config.get("repository_url", ""),
            branch=git_config.get("branch", "main"),
            token=git_config.get("token", ""),
            username=git_config.get("username", ""),
            email=git_config.get("email", ""),
        )