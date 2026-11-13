import threading
import time
from collections import defaultdict, deque

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def allow(key: str, limit: int, window: int = 60) -> bool:
    """Check and record a request using a sliding-window rate limit.

    Args:
        key: Identifier of the client, for example an IP address with a prefix.
        limit: Maximum number of requests allowed within the window.
        window: Window length in seconds.

    Returns:
        True if the request is allowed, False if the limit is exceeded.
    """
    now = time.time()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(_hits) > 5000:
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > window]:
                _hits.pop(k, None)
        return True
