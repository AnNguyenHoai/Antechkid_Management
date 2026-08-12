# -*- coding: utf-8 -*-
"""BusinessModuleRegistry - Register and manage business modules."""

import logging
from typing import Dict, List, Optional, Type

from .business_module import BusinessModule, BusinessModuleLifecycle

logger = logging.getLogger(__name__)


class BusinessModuleRegistry:
    """Registry for business modules."""

    def __init__(self):
        self._modules: Dict[str, BusinessModule] = {}

    def register(self, module: BusinessModule) -> None:
        """Register a business module."""
        name = module.get_name()
        if name in self._modules:
            logger.warning(f"Module {name} already registered, overwriting")
        self._modules[name] = module
        logger.info(f"Registered business module: {name} v{module.get_version()}")

    def get(self, name: str) -> Optional[BusinessModule]:
        """Get module by name."""
        return self._modules.get(name)

    def list_modules(self) -> List[str]:
        """List all registered module names."""
        return list(self._modules.keys())

    def initialize_all(self, context, event_bus) -> None:
        """Initialize all registered modules."""
        for name, module in self._modules.items():
            try:
                module.initialize(context, event_bus)
                logger.info(f"Initialized module: {name}")
            except Exception as e:
                logger.exception(f"Failed to initialize module {name}: {e}")

    def start_all(self) -> None:
        """Start all registered modules."""
        for name, module in self._modules.items():
            try:
                module.start()
                logger.info(f"Started module: {name}")
            except Exception as e:
                logger.exception(f"Failed to start module {name}: {e}")

    def stop_all(self) -> None:
        """Stop all registered modules."""
        for name, module in self._modules.items():
            try:
                module.stop()
                logger.info(f"Stopped module: {name}")
            except Exception as e:
                logger.exception(f"Failed to stop module {name}: {e}")

    def dispose_all(self) -> None:
        """Dispose all registered modules."""
        for name, module in self._modules.items():
            try:
                module.dispose()
                logger.info(f"Disposed module: {name}")
            except Exception as e:
                logger.exception(f"Failed to dispose module {name}: {e}")