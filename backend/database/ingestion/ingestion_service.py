from __future__ import annotations

import json
import re
import functools
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import urlparse

import fitz  # pymupdf
import httpx

from database.postgres_service import (
    batch_insert_chunks,
    update_file_status,
    update_file_chunk_count,
    get_all_models,
)
from database.embeddings import get_embeddings_model


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# LLM chunk analysis
# ---------------------------------------------------------------------------

CHUNK_ANALYSIS_PROMPT = """You are an academic content analyzer helping build a student knowledge base.

Analyze the following chunk of academic content and return a JSON object with these fields:

{{
  "concept_title": "One sentence describing the main concept in this chunk",
  "chunk_type": "one of: concept | definition | formula | example | summary",
  "keywords": ["term1", "term2", "term3"],
  "section_title": "The heading or topic this chunk belongs to (infer if not explicit)"
}}

Rules:
- chunk_type = "definition"  → chunk defines or explains what something IS
- chunk_type = "formula"     → chunk contains equations, math, or algorithms
- chunk_type = "example"     → chunk shows a worked example or case study
- chunk_type = "summary"     → chunk summarizes or concludes a topic
- chunk_type = "concept"     → everything else (explanations, descriptions)
- keywords: extract 3-7 important academic terms from the chunk
- concept_title: write it as a full sentence, not just a label
- Return ONLY valid JSON. No explanation, no markdown, no extra text.

Chunk:
\"\"\"
{chunk_text}
\"\"\"
"""


def _call_llm_sync(prompt: str, model: Dict) -> str:
    t    = model["type"]
    name = model["name"]
    key  = model.get("api_key") or ""
    url  = model.get("base_url") or ""

    with httpx.Client(timeout=30.0) as client:
        if t in ("ollama", "local"):
            p = urlparse(url or "http://localhost:11434")
            host = f"{p.scheme}://{p.netloc}"
            resp = client.post(
                f"{host}/api/generate",
                json={"model": name, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json()["response"]

        elif t == "openai":
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": name, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        elif t == "anthropic":
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": name, "max_tokens": 512,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]

        elif t == "gemini":
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent?key={key}"
            )
            resp = client.post(
                api_url,
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        elif t == "custom":
            base = url.rstrip("/")
            resp = client.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"} if key else {},
                json={"model": name, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    return ""


def _parse_json_response(text: str) -> Dict:
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _analyze_chunk(chunk_text: str, model: Dict) -> Dict:
    try:
        prompt = CHUNK_ANALYSIS_PROMPT.format(chunk_text=chunk_text)
        raw = _call_llm_sync(prompt, model)
        data = _parse_json_response(raw)
        return {
            "concept_title": data.get("concept_title", ""),
            "chunk_type":    data.get("chunk_type", "concept"),
            "keywords":      data.get("keywords", []),
            "section_title": data.get("section_title", ""),
        }
    except Exception as e:
        print(f"Chunk analysis skipped: {e}")
        return {}


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

def chunk_text(text: str, config: ChunkConfig | None = None) -> List[str]:
    if config is None:
        config = ChunkConfig()
    if not text or not text.strip():
        return []
    units = _split_into_units(text, config)
    chunks = _merge_units(units, config)
    chunks = _apply_overlap(chunks, config)
    return [c for c in chunks if len(c.strip()) >= 10]


@functools.lru_cache(maxsize=8)
def _compile_heading_re(patterns: tuple) -> re.Pattern:
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined)


def _is_heading(line: str, patterns: list) -> bool:
    return bool(_compile_heading_re(tuple(patterns)).match(line.strip()))


def _split_into_units(text: str, config: ChunkConfig) -> list:
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


def _split_sentences(text: str) -> list:
    _ABBREVS = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|al|Fig|No|Vol|pp)\.", re.IGNORECASE)
    protected = _ABBREVS.sub(lambda m: m.group(0).replace(".", "<!DOT!>"), text)
    protected = re.sub(r"(\d)\.(\d)", r"\1<!DOT!>\2", protected)
    raw = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'""«(]|\Z)", protected)
    return [s.replace("<!DOT!>", ".").strip() for s in raw if s.strip()]


def _hard_split(text: str, max_size: int) -> list:
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


def _merge_units(units: list, config: ChunkConfig) -> list:
    chunks: list[str] = []
    buffer: list[str] = []
    buf_len = [0]

    def flush():
        if buffer:
            chunks.append(" ".join(buffer).strip())
            buffer.clear()
            buf_len[0] = 0

    for unit in units:
        unit_len = len(unit.text)
        if unit.kind == "heading":
            flush()
            buffer.append(unit.text)
            buf_len[0] = unit_len
            continue
        if buf_len[0] + unit_len + 1 > config.max_size and buffer:
            flush()
        buffer.append(unit.text)
        buf_len[0] += unit_len + 1
        if buf_len[0] >= config.target_size:
            flush()

    flush()
    return chunks


def _apply_overlap(chunks: list, config: ChunkConfig) -> list:
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


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_pages(file_path: str) -> List[tuple]:
    """Return list of (page_number, raw_text) tuples."""
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return [(1, f.read())]


def _clean_text(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\S\n]", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"^ +$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------

_PARENT_CONFIG = ChunkConfig(target_size=800, max_size=1200, overlap=0)
_CHILD_CONFIG  = ChunkConfig(target_size=256, max_size=400,  overlap=30)


def ingest_and_store(file_path: str, file_id: int) -> None:
    try:
        update_file_status(file_id, "processing")

        # Resolve model for LLM analysis: prefer cloud models (always reachable)
        # over local/ollama which require a running local service.
        all_models = get_all_models()
        _cloud_types = {"gemini", "openai", "anthropic", "custom"}
        llm_model: Optional[Dict] = (
            next((m for m in all_models if m["type"] in _cloud_types), None)
            or next((m for m in all_models if m["is_default"]), None)
            or (all_models[0] if all_models else None)
        )

        embed_model = get_embeddings_model()
        pages = _extract_pages(file_path)

        # ── Pass 1: split into parent/child chunks, collect metadata ──────────
        records: List[Dict] = []   # chunk_index, content, parent_content, page_number
        chunk_index = 0

        for page_num, raw_text in pages:
            page_text = _clean_text(raw_text)
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

        if not records:
            update_file_chunk_count(file_id, 0)
            update_file_status(file_id, "ready")
            return

        # ── Pass 2: batch embed child + parent texts ───────────────────────────
        child_texts  = [r["content"]        for r in records]
        parent_texts = [r["parent_content"] for r in records]

        child_embeddings  = list(embed_model.embed(child_texts))
        parent_embeddings = list(embed_model.embed(parent_texts))

        # ── Pass 3: LLM analysis per child chunk ───────────────────────────────
        all_chunks: List[Dict] = []
        for i, rec in enumerate(records):
            analysis = _analyze_chunk(rec["content"], llm_model) if llm_model else {}
            all_chunks.append({
                **rec,
                "embedding":       list(child_embeddings[i]),
                "parent_embedding": list(parent_embeddings[i]),
                **analysis,
            })

        update_file_chunk_count(file_id, len(all_chunks))
        batch_insert_chunks(file_id, all_chunks)
        update_file_status(file_id, "ready")

    except Exception as e:
        print(f"Ingestion error for file {file_id}: {e}")
        update_file_status(file_id, "error")


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

def chunk_text_simple(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    config = ChunkConfig(target_size=chunk_size, max_size=int(chunk_size * 1.6), min_size=30, overlap=overlap)
    return chunk_text(text, config)
