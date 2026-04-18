from __future__ import annotations

import re
import functools
from dataclasses import dataclass, field
from typing import List

import fitz  # pymupdf
from database.postgres_service import batch_insert_embeddings, update_file_status, update_file_chunk_count
from database.embeddings import get_embeddings_model


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ChunkConfig:
    target_size: int = 500        # aim for chunks around this many chars
    max_size: int = 800           # hard ceiling before hard-split kicks in
    min_size: int = 80            # fragments smaller than this get merged
    overlap: int = 50             # chars of overlap between consecutive chunks
    heading_patterns: list = field(default_factory=lambda: [
        r"^#{1,6}\s+.+",         # Markdown headings
        r"^[A-Z][A-Z\s\d:,\-]{4,}$",  # ALL-CAPS lines (≥5 chars)
    ])


# ---------------------------------------------------------------------------
# Internal data structure
# ---------------------------------------------------------------------------

@dataclass
class TextUnit:
    """A labelled piece of text produced during the splitting phase."""
    text: str
    kind: str   # "heading" | "paragraph" | "sentence" | "fragment"
    heading_prefix: str = ""   # the heading text that owns this unit, if any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    config: ChunkConfig | None = None,
) -> List[str]:
    """
    Split *text* into semantically coherent chunks.

    Returns a list of non-empty strings.  Each string is at most
    ``config.max_size`` characters long (except when a single token
    genuinely cannot be split further).
    """
    if config is None:
        config = ChunkConfig()

    if not text or not text.strip():
        return []

    units = _split_into_units(text, config)
    chunks = _merge_units(units, config)
    chunks = _apply_overlap(chunks, config)
    return [c for c in chunks if len(c.strip()) >= 10]


# ---------------------------------------------------------------------------
# Step 1 — split into semantic units
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=8)
def _compile_heading_re(patterns: tuple[str, ...]) -> re.Pattern:
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined)


def _is_heading(line: str, patterns: list[str]) -> bool:
    """Return True if *line* looks like a section heading."""
    return bool(_compile_heading_re(tuple(patterns)).match(line.strip()))


def _split_into_units(text: str, config: ChunkConfig) -> list[TextUnit]:
    """
    Decompose *text* into a flat list of TextUnit objects.

    Order of operations
    -------------------
    1. Split on double-newlines to get paragraphs.
    2. Identify heading paragraphs; they become their own "heading" unit
       and are remembered as the current section header.
    3. Non-heading paragraphs that are within the target size become
       "paragraph" units directly.
    4. Non-heading paragraphs that exceed the target size are further
       split into sentences.
    5. Individual sentences that still exceed max_size are hard-split
       at the character boundary.
    """
    units: list[TextUnit] = []
    current_heading = ""

    # Split on one or more blank lines
    raw_blocks = re.split(r"\n{2,}", text.strip())

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        first_line = lines[0].strip()

        # --- Heading block ---
        if len(lines) == 1 and _is_heading(first_line, config.heading_patterns):
            current_heading = first_line
            units.append(TextUnit(text=first_line, kind="heading",
                                  heading_prefix=current_heading))
            continue

        # --- Normal paragraph ---
        if len(block) <= config.target_size:
            units.append(TextUnit(text=block, kind="paragraph",
                                  heading_prefix=current_heading))
        else:
            # Paragraph too big → sentence-split it
            sentences = _split_sentences(block)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sentence) <= config.max_size:
                    units.append(TextUnit(text=sentence, kind="sentence",
                                          heading_prefix=current_heading))
                else:
                    # Last resort: hard character split
                    for fragment in _hard_split(sentence, config.max_size):
                        units.append(TextUnit(text=fragment, kind="fragment",
                                              heading_prefix=current_heading))

    return units


def _split_sentences(text: str) -> list[str]:
    """
    Split *text* into sentences using punctuation boundaries.

    Handles:
    - Common abbreviations (Mr., Dr., vs., etc.) — not treated as sentence ends
    - Decimal numbers (3.14) — not treated as sentence ends
    - Ellipsis (…) — treated as a single sentence terminator
    """
    # Protect common abbreviations from being mis-split
    _ABBREVS = re.compile(
        r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|al|Fig|No|Vol|pp)\.",
        re.IGNORECASE,
    )
    protected = _ABBREVS.sub(lambda m: m.group(0).replace(".", "<!DOT!>"), text)
    # Protect decimal numbers
    protected = re.sub(r"(\d)\.(\d)", r"\1<!DOT!>\2", protected)

    # Split on . ! ? followed by whitespace and an uppercase letter or end-of-str
    raw = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'""«(]|\Z)", protected)

    restored = [s.replace("<!DOT!>", ".").strip() for s in raw]
    return [s for s in restored if s]


def _hard_split(text: str, max_size: int) -> list[str]:
    """Split *text* at word boundaries into pieces of at most *max_size* chars."""
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


# ---------------------------------------------------------------------------
# Step 2 — merge small units into target-sized chunks
# ---------------------------------------------------------------------------

def _merge_units(units: list[TextUnit], config: ChunkConfig) -> list[str]:
    """
    Greedily accumulate units into chunks.

    Rules
    -----
    - A "heading" unit always flushes the current buffer and starts fresh.
    - Adding a unit that would push the buffer past *max_size* flushes first.
    - After all units are consumed the remaining buffer is flushed.
    """
    chunks: list[str] = []
    buffer: list[str] = []

    def flush():
        if buffer:
            chunks.append(" ".join(buffer).strip())
            buffer.clear()

    nonlocal_buffer_len = [0]  # work around nonlocal limitation in nested fn

    for unit in units:
        unit_len = len(unit.text)

        if unit.kind == "heading":
            # Flush whatever we have, then start a new chunk with the heading
            flush()
            buffer.append(unit.text)
            nonlocal_buffer_len[0] = unit_len
            continue

        would_be = nonlocal_buffer_len[0] + unit_len + 1

        if would_be > config.max_size and buffer:
            flush()
            nonlocal_buffer_len[0] = 0

        buffer.append(unit.text)
        nonlocal_buffer_len[0] += unit_len + 1

        # Flush if we've hit or exceeded the target
        if nonlocal_buffer_len[0] >= config.target_size:
            flush()
            nonlocal_buffer_len[0] = 0

    flush()
    return chunks


# ---------------------------------------------------------------------------
# Step 3 — add overlap between consecutive chunks
# ---------------------------------------------------------------------------

def _apply_overlap(chunks: list[str], config: ChunkConfig) -> list[str]:
    """
    Prepend the tail of the previous chunk to each chunk so that the
    embedding model sees context across chunk boundaries.

    The overlap is taken at word boundaries so we never split a word.
    """
    if config.overlap <= 0 or len(chunks) < 2:
        return chunks

    result: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        tail = _word_boundary_tail(prev, config.overlap)
        result.append((tail + " " + chunks[i]).strip() if tail else chunks[i])

    return result


def _word_boundary_tail(text: str, n: int) -> str:
    """Return the last *n* characters of *text*, trimmed to a word boundary."""
    if len(text) <= n:
        return text
    tail = text[-n:]
    # Walk forward to the first space so we don't start mid-word
    space_idx = tail.find(" ")
    if space_idx == -1:
        return tail
    return tail[space_idx + 1:]


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

def _extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n\n".join(page.get_text() for page in doc)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _clean_text(text: str) -> str:
    # Normalize unicode to ASCII-compatible form
    import unicodedata
    text = unicodedata.normalize("NFKC", text)
    # Replace non-breaking and exotic spaces with regular space
    text = re.sub(r"[^\S\n]", " ", text)
    # Remove null bytes and control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse lines with only whitespace into blank lines
    text = re.sub(r"^ +$", "", text, flags=re.MULTILINE)
    # Collapse runs of 3+ blank lines into two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces on the same line into one
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def ingest_and_store(file_path: str, file_id: int) -> None:
    try:
        update_file_status(file_id, "processing")

        text = _clean_text(_extract_text(file_path))
        chunks = chunk_text(text)

        update_file_chunk_count(file_id, len(chunks))

        model = get_embeddings_model()
        items = [
            (index, chunk, list(list(model.embed([chunk]))[0]))
            for index, chunk in enumerate(chunks)
        ]

        batch_insert_embeddings(file_id, items)
        update_file_status(file_id, "ready")

    except Exception as e:
        print(f"Ingestion error for file {file_id}: {e}")
        update_file_status(file_id, "error")


# ---------------------------------------------------------------------------
# Convenience wrapper (same signature as the old chunk_text)
# ---------------------------------------------------------------------------

def chunk_text_simple(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """
    Drop-in replacement for the old character-based chunker.
    Delegates to the structure-aware implementation.
    """
    config = ChunkConfig(
        target_size=chunk_size,
        max_size=int(chunk_size * 1.6),
        min_size=30,
        overlap=overlap,
    )
    return chunk_text(text, config)