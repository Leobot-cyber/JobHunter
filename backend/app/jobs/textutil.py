from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(html: str, limit: int = 1200) -> str:
    if not html:
        return ""
    parser = _Stripper()
    try:
        parser.feed(html)
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def make_id(source: str, *parts: str) -> str:
    raw = "|".join([source, *[p or "" for p in parts]])
    return source + ":" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def keyword_hit(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    blob = text.lower()
    return any(k.lower() in blob for k in keywords if k.strip())


def split_keywords(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,，/|]+", raw) if p.strip()]
