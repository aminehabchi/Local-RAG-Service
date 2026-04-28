from __future__ import annotations

from typing import List

from fastembed import TextEmbedding

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model: TextEmbedding | None = None


def get_embeddings_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=_MODEL_NAME)
    return _model


def embed_texts(texts: List[str]):
    return list(get_embeddings_model().embed(texts))
