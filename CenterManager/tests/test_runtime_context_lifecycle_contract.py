from datetime import datetime

import pytest

from centermanager.platform.context import RuntimeContext
from centermanager.platform.runtime.context.runtime_context import RuntimeContext as CanonicalRuntimeContext
from centermanager.platform.runtime.context_manager import RuntimeContextManager


def test_public_runtime_context_is_canonical_type():
    assert RuntimeContext is CanonicalRuntimeContext


def test_install_context_uses_public_manager_boundary():
    manager = RuntimeContextManager()
    context = RuntimeContext(created_at=datetime.now())

    assert manager.install_context(context) is context
    assert manager.get_context() is context


def test_install_context_rejects_replacement_context():
    manager = RuntimeContextManager()
    first = RuntimeContext()
    second = RuntimeContext()
    manager.install_context(first)

    with pytest.raises(RuntimeError, match="already installed"):
        manager.install_context(second)
