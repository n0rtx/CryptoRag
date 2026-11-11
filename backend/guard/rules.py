"""Дешёвые правила до ML-классификатора: длина, мусор, prompt-injection."""
import re

_INJECTION = re.compile(
    r"(ignore (all |the )?(previous|above|prior) (instructions|prompts?)|disregard .{0,30}instructions|"
    r"system prompt|reveal .{0,20}(prompt|instructions|api key)|you are now|jailbreak|\bDAN\b|"
    r"игнорируй (все )?(предыдущие|прошлые|выше)|забудь (все )?(инструкции|предыдущие)|"
    r"системн(ый|ого) промпт|покажи (свой )?(промпт|инструкции|ключ))",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://|www\.|t\.me/", re.IGNORECASE)


def check(text: str, max_chars: int) -> str | None:
    """None — прошло; иначе строка-причина отказа."""
    t = text.strip()
    if len(t) < 2:
        return "empty"
    if len(t) > max_chars:
        return "too_long"
    if not re.search(r"[A-Za-zА-Яа-яЁё]{2}", t):
        return "no_letters"
    if _INJECTION.search(t):
        return "injection"
    if len(_URL.findall(t)) >= 2:
        return "spam_links"
    if re.search(r"(.)\1{9,}", t):  # "аааааааааа"
        return "gibberish"
    return None
