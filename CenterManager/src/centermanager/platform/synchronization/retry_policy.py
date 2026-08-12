# -*- coding: utf-8 -*-
"""RetryPolicy - Retry configuration for operations."""

from dataclasses import dataclass, field
from typing import Optional, Callable
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Retry policy for operations."""
    
    max_retries: int = 3
    retry_interval: float = 1.0  # seconds
    backoff_factor: float = 2.0
    max_interval: float = 30.0
    
    def execute(self, operation: Callable[[], bool], name: str = "operation") -> bool:
        """
        Execute operation with retry.
        Returns True if operation succeeds within retries.
        """
        attempt = 0
        interval = self.retry_interval
        
        while attempt <= self.max_retries:
            try:
                if operation():
                    if attempt > 0:
                        logger.info(f"{name} succeeded after {attempt} retries")
                    return True
            except Exception as e:
                logger.warning(f"{name} failed (attempt {attempt}): {e}")
            
            if attempt >= self.max_retries:
                logger.error(f"{name} failed after {self.max_retries} retries")
                return False
            
            # Wait before next retry
            time.sleep(interval)
            interval = min(interval * self.backoff_factor, self.max_interval)
            attempt += 1
        
        return False
    
    def execute_with_result(self, operation: Callable) -> tuple:
        """
        Execute operation and return (success, result).
        Result is the return value of operation.
        """
        attempt = 0
        interval = self.retry_interval
        last_result = None
        
        while attempt <= self.max_retries:
            try:
                result = operation()
                if result is True or result is not None:
                    return True, result
                last_result = result
            except Exception as e:
                logger.warning(f"Operation failed (attempt {attempt}): {e}")
                last_result = None
            
            if attempt >= self.max_retries:
                break
            
            time.sleep(interval)
            interval = min(interval * self.backoff_factor, self.max_interval)
            attempt += 1
        
        return False, last_result