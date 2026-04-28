from __future__ import annotations

import re
import functools
from dataclasses import dataclass, field
from typing import List, Dict

import fitz  # pymupdf

_ABBREVS = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|al|Fig|No|Vol|pp)\.",
    re.IGNORECASE,
)


@dataclass
class ChunkConfig:
    target_size: int = 500
    max_size: int = 800
    min_size: int = 80
    overlap: int = 50
    heading_patterns: list = field(default_factory=lambda: [
        r"^#{1,6}\s+.+",
        r"^[A-Z][A-Z\s\d:,\-]{4,}$",
    ])


@dataclass
class TextUnit:
    text: str
    kind: str
    heading_prefix: str = ""


_PARENT_CONFIG = ChunkConfig(target_size=800, max_size=1200, overlap=0)
_CHILD_CONFIG  = ChunkConfig(target_size=256, max_size=400,  overlap=30)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pages(file_path: str) -> List[tuple]:
    """Return list of (page_number, raw_text) tuples."""
    if file_path.endswith(".pdf"):
        with fitz.open(file_path) as doc:
            return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return [(1, f.read())]


def build_records(pages: List[tuple]) -> List[Dict]:
    """
    Split cleaned pages into parent/child chunk records.
    Each record: chunk_index, content (child), parent_content, page_number.
    """
    records: List[Dict] = []
    chunk_index = 0
    for page_num, page_text in pages:
        if not page_text.strip():
            continue
        for parent_chunk in chunk_text(page_text, _PARENT_CONFIG):
            child_chunks = chunk_text(parent_chunk, _CHILD_CONFIG) or [parent_chunk]
            for child_chunk in child_chunks:
                records.append({
                    "chunk_index":    chunk_index,
                    "content":        child_chunk,
                    "parent_content": parent_chunk,
                    "page_number":    page_num,
                })
                chunk_index += 1
    return records


def chunk_text(text: str, config: ChunkConfig | None = None) -> List[str]:
    if config is None:
        config = ChunkConfig()
    if not text or not text.strip():
        return []
    units = _split_into_units(text, config)
    chunks = _merge_units(units, config)
    chunks = _apply_overlap(chunks, config)
    return [c for c in chunks if len(c.strip()) >= 10]


# ---------------------------------------------------------------------------
# Sentence-based splitting helpers
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=8)
def _compile_heading_re(patterns: tuple) -> re.Pattern:
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined)


def _is_heading(line: str, patterns: list) -> bool:
    return bool(_compile_heading_re(tuple(patterns)).match(line.strip()))


def _split_sentences(text: str) -> List[str]:
    protected = _ABBREVS.sub(lambda m: m.group(0).replace(".", "<!DOT!>"), text)
    protected = re.sub(r"(\d)\.(\d)", r"\1<!DOT!>\2", protected)
    raw = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'""«(]|\Z)", protected)
    return [s.replace("<!DOT!>", ".").strip() for s in raw if s.strip()]


def _hard_split(text: str, max_size: int) -> List[str]:
    words = text.split()
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_size and current:
            pieces.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces


def _split_into_units(text: str, config: ChunkConfig) -> List[TextUnit]:
    units: list[TextUnit] = []
    current_heading = ""
    raw_blocks = re.split(r"\n{2,}", text.strip())

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        first_line = lines[0].strip()

        if len(lines) == 1 and _is_heading(first_line, config.heading_patterns):
            current_heading = first_line
            units.append(TextUnit(text=first_line, kind="heading", heading_prefix=current_heading))
            continue

        if len(block) <= config.target_size:
            units.append(TextUnit(text=block, kind="paragraph", heading_prefix=current_heading))
        else:
            for sentence in _split_sentences(block):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sentence) <= config.max_size:
                    units.append(TextUnit(text=sentence, kind="sentence", heading_prefix=current_heading))
                else:
                    for fragment in _hard_split(sentence, config.max_size):
                        units.append(TextUnit(text=fragment, kind="fragment", heading_prefix=current_heading))

    return units


def _merge_units(units: List[TextUnit], config: ChunkConfig) -> List[str]:
    chunks: list[str] = []
    buffer: list[str] = []
    buf_len = 0

    def flush():
        nonlocal buf_len
        if buffer:
            chunks.append(" ".join(buffer).strip())
            buffer.clear()
            buf_len = 0

    for unit in units:
        unit_len = len(unit.text)
        if unit.kind == "heading":
            flush()
            buffer.append(unit.text)
            buf_len = unit_len
            continue
        if buf_len + unit_len + 1 > config.max_size and buffer:
            flush()
        buffer.append(unit.text)
        buf_len += unit_len + 1
        if buf_len >= config.target_size:
            flush()

    flush()
    return chunks


def _apply_overlap(chunks: List[str], config: ChunkConfig) -> List[str]:
    if config.overlap <= 0 or len(chunks) < 2:
        return chunks
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = _word_boundary_tail(chunks[i - 1], config.overlap)
        result.append((tail + " " + chunks[i]).strip() if tail else chunks[i])
    return result


def _word_boundary_tail(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    tail = text[-n:]
    space_idx = tail.find(" ")
    return tail if space_idx == -1 else tail[space_idx + 1:]
