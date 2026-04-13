"""OKX common utilities for cryptocurrency exchange data.

Provides shared exception classes, rate-limiting decorators, and helper functions
for interacting with OKX exchange via CCXT library.
"""

import time
import logging
from typing import Callable, Any
import ccxt

logger = logging.getLogger(__name__)


class OKXRateLimitError(Exception):
    """Exception raised when OKX API rate limit is exceeded via CCXT."""
    pass


def okx_retry(func: Callable[[], Any], max_retries: int = 3, base_delay: float = 2.0) -> Any:
    """Execute a CCXT OKX call with exponential backoff on rate limits.

    CCXT may raise various rate-limiting exceptions (RateLimitExceeded,
    DDoSProtection, etc.). This wrapper adds retry logic for rate limits
    and network errors. Other exceptions propagate immediately.

    Args:
        func: Callable that makes the CCXT API call
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Base delay in seconds for exponential backoff (default 2.0)

    Returns:
        The result of func()

    Raises:
        OKXRateLimitError: If rate limit persists after max_retries
        Exception: Any other exception from func() is propagated
    """
    # Define exceptions that indicate rate limiting or temporary issues
    rate_limit_exceptions = []
    network_exceptions = (ccxt.NetworkError, ccxt.RequestTimeout)

    # Try to add CCXT-specific rate limit exceptions if they exist
    try:
        if hasattr(ccxt, 'RateLimitExceeded'):
            rate_limit_exceptions.append(ccxt.RateLimitExceeded)
        if hasattr(ccxt, 'DDoSProtection'):
            rate_limit_exceptions.append(ccxt.DDoSProtection)
        if hasattr(ccxt, 'ExchangeNotAvailable'):
            rate_limit_exceptions.append(ccxt.ExchangeNotAvailable)
    except AttributeError:
        pass

    # Convert to tuples for exception catching
    rate_limit_exceptions = tuple(rate_limit_exceptions)
    all_retry_exceptions = rate_limit_exceptions + network_exceptions

    for attempt in range(max_retries + 1):
        try:
            return func()
        except all_retry_exceptions as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                exception_name = e.__class__.__name__
                logger.warning(
                    f"OKX API error ({exception_name}), retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
            else:
                # If it's a rate limit exception, raise OKXRateLimitError
                if isinstance(e, rate_limit_exceptions):
                    raise OKXRateLimitError(
                        f"OKX rate limit exceeded after {max_retries} retries: {e}"
                    )
                else:
                    raise


def okx_request_limiter(delay_ms: int = 200):
    """Decorator to add minimum delay between OKX API requests.

    This helps avoid hitting OKX rate limits by enforcing a minimum
    time between consecutive calls. OKX limits: 10 requests per 2 seconds
    per IP + instrument (≈200ms between requests).

    Args:
        delay_ms: Minimum delay between calls in milliseconds (default 200)

    Returns:
        Decorator function
    """
    def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
        last_call_time = 0

        def wrapper(*args, **kwargs) -> Any:
            nonlocal last_call_time
            current_time = time.time() * 1000  # Convert to ms

            # Calculate time since last call
            time_since_last = current_time - last_call_time
            if time_since_last < delay_ms:
                sleep_time = (delay_ms - time_since_last) / 1000.0
                logger.debug(f"Rate limiting OKX call: sleeping {sleep_time:.3f}s")
                time.sleep(sleep_time)

            result = func(*args, **kwargs)
            last_call_time = time.time() * 1000
            return result

        return wrapper

    return decorator


def _get_okx_exchange(config: dict = None) -> ccxt.Exchange:
    """Create and return a CCXT OKX exchange instance.

    Args:
        config: Optional configuration dict. If None, uses get_config()

    Returns:
        ccxt.okx exchange instance (or other exchange if configured)

    Raises:
        ValueError: If the exchange is not available in CCXT
    """
    from .config import get_config

    if config is None:
        config = get_config()

    exchange_id = config.get("ccxt_exchange", "okx")

    # For OKX-specific data, we should use OKX exchange
    # But allow configuration for consistency with other CCXT calls
    if exchange_id.lower() != "okx":
        logger.warning(
            f"OKX data vendor configured with exchange '{exchange_id}', "
            f"but OKX-specific endpoints require OKX exchange. "
            f"Using 'okx' instead."
        )
        exchange_id = "okx"

    try:
        exchange_class = getattr(ccxt, exchange_id)
        return exchange_class()
    except AttributeError:
        raise ValueError(
            f"CCXT exchange '{exchange_id}' not found. "
            f"Make sure you have a CCXT version that supports it."
        )


def parse_okx_timestamp(timestamp_ms: int) -> str:
    """Convert OKX timestamp (milliseconds) to ISO 8601 string.

    Args:
        timestamp_ms: Timestamp in milliseconds

    Returns:
        ISO 8601 formatted string (YYYY-MM-DDTHH:MM:SS)
    """
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def format_okx_date(date_str: str) -> str:
    """Convert date string to OKX-compatible format.

    OKX API endpoints often require timestamps in milliseconds or
    specific date formats. This function helps with common conversions.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Timestamp in milliseconds as string
    """
    from datetime import datetime
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return str(int(dt.timestamp() * 1000))