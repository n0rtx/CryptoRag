import logging
import threading

import joblib

from .. import config
from ..coins import detect_coins
from . import rules

log = logging.getLogger(__name__)
_model = None
_lock = threading.Lock()


def _load():
    """Load the trained filter model once and cache it.

    Returns:
        The model, or None if it has not been trained yet.
    """
    global _model
    with _lock:
        if _model is None and config.MODEL_PATH.exists():
            _model = joblib.load(config.MODEL_PATH)
            log.info("Фильтр загружен: %s", config.MODEL_PATH)
    return _model


def evaluate(text: str) -> dict:
    """Decide whether a question should reach the LLM.

    Combines the rule checks, coin detection and the ML relevance score.

    Args:
        text: User question.

    Returns:
        A dictionary with ``allowed``, ``reason``, ``score`` and ``coins``.
    """
    reason = rules.check(text, config.MAX_QUESTION_CHARS)
    if reason:
        return {"allowed": False, "reason": reason, "score": None, "coins": []}

    coins = detect_coins(text)
    model = _load()
    if model is None:
        log.warning("Модель фильтра не найдена, запустите scripts/train_filter.py")
        return {"allowed": True, "reason": "no_model", "score": None, "coins": coins}

    score = float(model.predict_proba([text.lower()])[0][1])
    eff = max(score, 0.6) if coins else score
    allowed = eff >= config.FILTER_THRESHOLD
    return {"allowed": allowed, "reason": "ok" if allowed else "off_topic", "score": round(score, 3), "coins": coins}
