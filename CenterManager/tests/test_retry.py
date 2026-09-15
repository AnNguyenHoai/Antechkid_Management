# -*- coding: utf-8 -*-
import pytest
import time
from centermanager.platform.retry import RetryPolicy, retry


def test_retry_success():
    policy = RetryPolicy(max_retries=3)
    result = policy.execute(lambda: 42)
    assert result == 42


def test_retry_with_exception():
    counter = 0

    def failing_func():
        nonlocal counter
        counter += 1
        if counter < 3:
            raise ValueError("Temporary error")
        return "success"

    policy = RetryPolicy(max_retries=3, base_delay=0.01)
    result = policy.execute(failing_func)
    assert result == "success"
    assert counter == 3


def test_retry_with_bool_false():
    counter = 0

    def failing_func():
        nonlocal counter
        counter += 1
        return counter >= 3

    policy = RetryPolicy(max_retries=3, base_delay=0.01, retry_on_return_false=True)
    result = policy.execute(failing_func)
    assert result is True
    assert counter == 3


def test_retry_exhausted():
    def always_fail():
        raise ValueError("Always fail")

    policy = RetryPolicy(max_retries=2, base_delay=0.01)
    with pytest.raises(ValueError, match="Always fail"):
        policy.execute(always_fail)