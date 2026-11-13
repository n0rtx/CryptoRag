import logging
import threading

from . import config, market

log = logging.getLogger(__name__)

RETRY_SECONDS = 300

_thread: threading.Thread | None = None
_stop = threading.Event()


def _initial_wait() -> float:
    """Compute how long to wait before the first background refresh.

    Returns:
        Zero if data is missing, otherwise the time left until the snapshot reaches the refresh interval.
    """
    age = market.snapshot_age()
    if age is None:
        return 0.0
    return max(0.0, config.MARKET_REFRESH_SECONDS - age)


def _loop() -> None:
    """Refresh market data periodically until the process stops.

    After a failed or partial refresh the loop retries after a few minutes instead of waiting for the full interval.
    """
    wait = _initial_wait()
    while not _stop.wait(wait):
        try:
            ok = market.refresh_all()
        except Exception:
            log.exception("Background market refresh crashed")
            ok = False
        wait = config.MARKET_REFRESH_SECONDS if ok else min(config.MARKET_REFRESH_SECONDS, RETRY_SECONDS)


def start() -> None:
    """Start the background refresh thread once per process, if it is enabled in the settings."""
    global _thread
    if not config.MARKET_BACKGROUND or (_thread is not None and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="market-refresh", daemon=True)
    _thread.start()
    log.info("Market refresh scheduler started (every %d s)", config.MARKET_REFRESH_SECONDS)
