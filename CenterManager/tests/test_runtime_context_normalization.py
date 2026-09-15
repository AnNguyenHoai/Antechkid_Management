import importlib


def test_runtime_context_has_single_public_type():
    public_module = importlib.import_module("centermanager.platform.context.runtime_context")
    runtime_module = importlib.import_module("centermanager.platform.runtime.context.runtime_context")

    assert public_module.RuntimeContext is runtime_module.RuntimeContext


def test_platform_context_default_uses_canonical_runtime_context():
    from centermanager.platform.context import PlatformContext
    from centermanager.platform.runtime.context.runtime_context import RuntimeContext

    context = PlatformContext.create_default()

    assert isinstance(context.runtime, RuntimeContext)
    assert context.runtime.context_id
    assert context.runtime.session is None
    assert context.runtime.configuration is not None


def test_runtime_context_manager_uses_same_runtime_context_type():
    from centermanager.platform.context import RuntimeContext as PublicRuntimeContext
    from centermanager.platform.runtime.context_manager import RuntimeContextManager

    manager = RuntimeContextManager()
    context = manager.create_context()

    assert type(context) is PublicRuntimeContext
    assert context.configuration is not None
    assert context.session is None
