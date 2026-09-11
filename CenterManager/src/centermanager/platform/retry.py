# -*- coding: utf-8 -*-
"""
RetryPolicy - configurable retry with exponential backoff.
"""
import logging
import time
from typing import Callable, Type, Tuple, Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        retry_on_return_false: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.retry_on_exceptions = retry_on_exceptions
        self.retry_on_return_false = retry_on_return_false

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)

                # If function returns bool False and we should retry on False
                if self.retry_on_return_false and result is False:
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(f"Retry {attempt+1}/{self.max_retries}: function returned False, retrying in {delay:.2f}s")
                        time.sleep(delay)
                        continue
                    return False

                return result

            except self.retry_on_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Retry {attempt+1}/{self.max_retries}: {e.__class__.__name__}: {e}, retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retries failed: {e}")
                    raise

        if last_exception:
            raise last_exception
        return None

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)


def retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_on_return_false: bool = True,
):
    """Decorator for retry policy."""
    policy = RetryPolicy(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        retry_on_exceptions=retry_on_exceptions,
        retry_on_return_false=retry_on_return_false,
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return policy.execute(func, *args, **kwargs)
        return wrapper

    return decorator