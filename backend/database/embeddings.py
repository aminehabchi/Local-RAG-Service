from fastembed import TextEmbedding

_model: TextEmbedding | None = None


def get_embeddings_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model
