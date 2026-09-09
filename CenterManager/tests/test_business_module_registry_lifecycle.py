from centermanager.platform.business import BusinessModule, BusinessModuleLifecycle, BusinessModuleRegistry


class FakeModule(BusinessModule):
    def __init__(self, name, events, fail_initialize=False, fail_start=False):
        self._name = name
        self._events = events
        self._fail_initialize = fail_initialize
        self._fail_start = fail_start

    def initialize(self, context, event_bus):
        self._events.append(f"initialize:{self._name}")
        if self._fail_initialize:
            raise RuntimeError(f"initialize failed: {self._name}")

    def start(self):
        self._events.append(f"start:{self._name}")
        if self._fail_start:
            raise RuntimeError(f"start failed: {self._name}")

    def stop(self):
        self._events.append(f"stop:{self._name}")

    def dispose(self):
        self._events.append(f"dispose:{self._name}")

    def get_name(self):
        return self._name

    def get_version(self):
        return "1.0.0"

    def get_descriptors(self):
        return []


def test_registry_initializes_and_starts_in_registration_order_and_stops_in_reverse():
    events = []
    registry = BusinessModuleRegistry()
    registry.register(FakeModule("a", events))
    registry.register(FakeModule("b", events))

    registry.initialize_all(object(), object())
    registry.start_all()

    assert registry.is_initialized()
    assert registry.is_started()
    assert events == ["initialize:a", "initialize:b", "start:a", "start:b"]

    registry.stop_all()
    registry.dispose_all()

    assert events == [
        "initialize:a", "initialize:b", "start:a", "start:b",
        "stop:b", "stop:a", "dispose:b", "dispose:a",
    ]


def test_registry_rejects_duplicate_registration():
    registry = BusinessModuleRegistry()
    registry.register(FakeModule("a", []))

    try:
        registry.register(FakeModule("a", []))
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration must fail")


def test_registry_requires_initialization_before_start():
    registry = BusinessModuleRegistry()
    registry.register(FakeModule("a", []))

    try:
        registry.start_all()
    except RuntimeError as exc:
        assert "Cannot start module a" in str(exc)
    else:
        raise AssertionError("starting an uninitialized module must fail")


def test_registry_propagates_initialize_failure():
    events = []
    registry = BusinessModuleRegistry()
    registry.register(FakeModule("a", events))
    registry.register(FakeModule("b", events, fail_initialize=True))

    try:
        registry.initialize_all(object(), object())
    except RuntimeError as exc:
        assert "initialize failed: b" in str(exc)
    else:
        raise AssertionError("initialization failure must propagate")

    assert events == ["initialize:a", "initialize:b"]
    assert registry.get("a").get_lifecycle() is BusinessModuleLifecycle.INITIALIZED
    assert registry.get("b").get_lifecycle() is BusinessModuleLifecycle.UNINITIALIZED
