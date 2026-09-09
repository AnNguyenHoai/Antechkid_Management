# -*- coding: utf-8 -*-
"""Public RuntimeContext compatibility import.

The concrete RuntimeContext is owned by the runtime context package. This
module remains as the stable public import path used by PlatformContext and
existing consumers, but it deliberately contains no second RuntimeContext
implementation.
"""

from centermanager.platform.runtime.context.runtime_context import RuntimeContext

__all__ = ["RuntimeContext"]
