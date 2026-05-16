"""Common utilities for the akshare data vendor: retry logic and rate limiting."""

import time
import logging
from json import JSONDecodeError
from typing import Callable, Any

import requests

logger = logging.getLogger(__name__)


class AkshareNetworkError(Exception):
    """Persistent network / rate-limit error after all retries are exhausted."""
    pass


def akshare_retry(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 2.0,
    pre_delay: float = 0.5,
) -> Any:
    """Execute an akshare call with throttle delay and exponential backoff.

    Args:
        func: Zero-argument callable wrapping the akshare API call.
        max_retries: Maximum number of retry attempts after the first failure.
        base_delay: Base delay in seconds for exponential backoff (2→4→8s).
        pre_delay: Fixed sleep before the first attempt (replaces _throttle).

    Retries on requests-level network errors and known akshare transient flakes
    (JSONDecodeError, KeyError). Other exceptions propagate immediately so
    real programming bugs surface fast.

    Raises:
        AkshareNetworkError: After max_retries exhausted on retryable errors.
        Any non-retryable exception from func: propagated without retry.
    """
    time.sleep(pre_delay)

    _network_excs = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
        requests.exceptions.ChunkedEncodingError,
    )
    _flake_excs = (JSONDecodeError, KeyError)
    _retryable = _network_excs + _flake_excs

    for attempt in range(max_retries + 1):
        try:
            return func()
        except _retryable as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "akshare call failed (%s: %s), retrying in %.1fs "
                    "(attempt %d/%d)",
                    type(e).__name__, e, delay, attempt + 1, max_retries,
                )
                time.sleep(delay)
            else:
                raise AkshareNetworkError(
                    f"akshare call failed after {max_retries} retries: {e}"
                ) from e
