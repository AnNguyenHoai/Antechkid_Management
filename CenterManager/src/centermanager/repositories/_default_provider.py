"""Composition-boundary helpers for repository providers."""
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider


def create_default_repository_provider() -> RepositoryProvider:
    """Create a fresh production repository provider."""
    return SqlAlchemyRepositoryProvider()
