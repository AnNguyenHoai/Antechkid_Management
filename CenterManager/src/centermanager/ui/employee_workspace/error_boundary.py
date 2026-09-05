from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from centermanager.core.current_user import get_current_user

logger = logging.getLogger(__name__)


def log_ui_exception(
    logger_obj: logging.Logger,
    *,
    operation: str,
    exc: BaseException,
    employee_id: Optional[int] = None,
    record_id: Optional[int] = None,
    capability: Optional[str] = None,
    **context: Any,
) -> None:
    """Log one Employee Workspace UI failure with structured operational context."""
    user = get_current_user()
    logger_obj.exception(
        "[EMPLOYEE_WORKSPACE_ERROR] operation=%s user_id=%s employee_id=%s "
        "record_id=%s capability=%s exception_type=%s exception=%s context=%s",
        operation,
        getattr(user, "id", None),
        employee_id,
        record_id,
        capability,
        type(exc).__name__,
        exc,
        context or None,
    )


def execute_ui_operation(
    *,
    logger_obj: logging.Logger,
    operation: str,
    action: Callable[[], Any],
    on_error: Callable[[Exception], None],
    employee_id: Optional[int] = None,
    record_id: Optional[int] = None,
    capability: Optional[str] = None,
    **context: Any,
) -> bool:
    """Execute a UI operation and guarantee a logged exception before UI handling."""
    try:
        action()
        return True
    except Exception as exc:
        log_ui_exception(
            logger_obj,
            operation=operation,
            exc=exc,
            employee_id=employee_id,
            record_id=record_id,
            capability=capability,
            **context,
        )
        on_error(exc)
        return False
