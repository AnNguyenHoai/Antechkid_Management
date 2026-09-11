# -*- coding: utf-8 -*-
"""BusinessModuleRegistry - Register and manage business modules."""

import logging
from typing import Dict, List, Optional

from .business_module import BusinessModule, BusinessModuleLifecycle

logger = logging.getLogger(__name__)


class BusinessModuleRegistry:
    """Registry for business modules and their platform-owned lifecycle."""

    def __init__(self):
        self._modules: Dict[str, BusinessModule] = {}
        self._initialized: List[str] = []
        self._started: List[str] = []

    def register(self, module: BusinessModule) -> None:
        """Register a business module exactly once.

        Duplicate module ids are rejected rather than silently replacing a
        live module. A duplicate registration is almost always a wiring error
        and must not change the lifecycle owner behind the registry's back.
        """
        name = module.get_name()
        if not name:
            raise ValueError("Business module name must not be empty")
        if name in self._modules:
            raise ValueError(f"Business module already registered: {name}")
        if module.get_lifecycle() is not BusinessModuleLifecycle.UNINITIALIZED:
            raise ValueError(
                f"Business module {name} must be UNINITIALIZED when registered"
            )
        self._modules[name] = module
        logger.info("Registered business module: %s v%s", name, module.get_version())

    def get(self, name: str) -> Optional[BusinessModule]:
        """Get module by name."""
        return self._modules.get(name)

    def list_modules(self) -> List[str]:
        """List all registered module names in registration order."""
        return list(self._modules.keys())

    def initialize_all(self, context, event_bus) -> None:
        """Initialize all modules in registration order.

        Lifecycle failures are propagated. Swallowing an initialization error
        leaves the application with a partially initialized module graph while
        callers believe initialization succeeded.
        """
        for name, module in self._modules.items():
            if module.get_lifecycle() is BusinessModuleLifecycle.INITIALIZED:
                continue
            if module.get_lifecycle() is not BusinessModuleLifecycle.UNINITIALIZED:
                raise RuntimeError(
                    f"Cannot initialize module {name} from state "
                    f"{module.get_lifecycle().value}"
                )
            module.initialize(context, event_bus)
            module._set_lifecycle(BusinessModuleLifecycle.INITIALIZED)
            self._initialized.append(name)
            logger.info("Initialized module: %s", name)

    def start_all(self) -> None:
        """Start all initialized modules in registration order."""
        for name, module in self._modules.items():
            if module.get_lifecycle() is BusinessModuleLifecycle.STARTED:
                continue
            if module.get_lifecycle() is not BusinessModuleLifecycle.INITIALIZED:
                raise RuntimeError(
                    f"Cannot start module {name} from state "
                    f"{module.get_lifecycle().value}"
                )
            module.start()
            module._set_lifecycle(BusinessModuleLifecycle.STARTED)
            self._started.append(name)
            logger.info("Started module: %s", name)

    def stop_all(self) -> None:
        """Stop started modules in reverse dependency/registration order."""
        for name in reversed(self._started):
            module = self._modules[name]
            try:
                if module.get_lifecycle() is BusinessModuleLifecycle.STARTED:
                    module._set_lifecycle(BusinessModuleLifecycle.STOPPING)
                    module.stop()
                    module._set_lifecycle(BusinessModuleLifecycle.STOPPED)
                    logger.info("Stopped module: %s", name)
            finally:
                if name in self._started:
                    self._started.remove(name)

    def dispose_all(self) -> None:
        """Dispose modules in reverse registration order after stopping them."""
        self.stop_all()
        for name in reversed(self._initialized):
            module = self._modules[name]
            try:
                if module.get_lifecycle() is not BusinessModuleLifecycle.STOPPED:
                    raise RuntimeError(
                        f"Cannot dispose module {name} from state "
                        f"{module.get_lifecycle().value}"
                    )
                module.dispose()
                logger.info("Disposed module: %s", name)
            finally:
                if name in self._initialized:
                    self._initialized.remove(name)

    def is_initialized(self) -> bool:
        """Return whether every registered module has been initialized."""
        return all(
            module.get_lifecycle() is not BusinessModuleLifecycle.UNINITIALIZED
            for module in self._modules.values()
        )

    def is_started(self) -> bool:
        """Return whether every registered module is started."""
        return all(
            module.get_lifecycle() is BusinessModuleLifecycle.STARTED
            for module in self._modules.values()
        )
