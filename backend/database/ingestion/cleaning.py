from __future__ import annotations

import re
import unicodedata
from typing import List


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\S\n]", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"^ +$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def clean_pages(pages: List[tuple]) -> List[tuple]:
    result = []
    for page_num, raw_text in pages:
        cleaned = clean_text(raw_text)
        if cleaned:
            result.append((page_num, cleaned))
    return result
