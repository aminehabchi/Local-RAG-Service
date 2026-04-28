from __future__ import annotations

import re
import unicodedata


def clean_query(text: str) -> str:
    """Normalize and sanitize a search query before embedding or keyword search."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text
