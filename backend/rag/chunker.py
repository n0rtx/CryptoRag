import re

MAX_CHARS = 900
OVERLAP = 120


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split a markdown document into overlapping chunks.

    The document is split by headings and then by paragraphs, and the heading is prepended to each chunk.

    Args:
        text: Markdown source.
        source: Name of the document, stored in each chunk.

    Returns:
        A list of chunk dictionaries with ``source``, ``title`` and ``text``.
    """
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
    """Build a chunk dictionary.

    Args:
        source: Name of the source document.
        title: Section heading.
        text: Chunk body.

    Returns:
        A chunk dictionary with the heading prepended to the text.
    """
    prefix = f"{title}\n" if title else ""
    return {"source": source, "title": title, "text": prefix + text}
