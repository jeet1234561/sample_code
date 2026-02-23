import asyncio
import functools
import logging

logger = logging.getLogger("epiap.retry")


def async_retry(max_retries: int = 3, backoff_base: float = 2.0, exceptions=(Exception,)):
    """Decorator for exponential backoff retry on async functions.

    Satisfies FRD requirement: "Response failures auto-retry with exponential back-off."
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait = backoff_base ** attempt
                        logger.warning(
                            f"[Retry] {func.__name__} attempt {attempt + 1}/{max_retries} "
                            f"failed: {e}. Retrying in {wait}s..."
                        )
                        await asyncio.sleep(wait)
            raise last_exception

        return wrapper

    return decorator
