"""Нарезка markdown-документов на чанки по заголовкам/абзацам."""
import re

MAX_CHARS = 900
OVERLAP = 120


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Делит по заголовкам '#', затем по абзацам до MAX_CHARS. Заголовок добавляется к каждому чанку."""
    sections: list[tuple[str, str]] = []
    title, buf = "", []
    for line in text.splitlines():
        if re.match(r"^#{1,3}\s", line):
            if buf:
                sections.append((title, "\n".join(buf).strip()))
            title, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if buf:
        sections.append((title, "\n".join(buf).strip()))

    chunks: list[dict] = []
    for title, body in sections:
        if not body:
            continue
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        cur = ""
        for p in paras:
            if cur and len(cur) + len(p) > MAX_CHARS:
                chunks.append(_mk(source, title, cur))
                cur = cur[-OVERLAP:] + "\n" + p
            else:
                cur = f"{cur}\n\n{p}".strip()
        if cur:
            chunks.append(_mk(source, title, cur))
    return chunks


def _mk(source: str, title: str, text: str) -> dict:
    prefix = f"{title}\n" if title else ""
    return {"source": source, "title": title, "text": prefix + text}
