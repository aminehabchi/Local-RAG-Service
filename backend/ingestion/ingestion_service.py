from typing import List, Dict
from langchain_ollama import OllamaEmbeddings
from ingestion.ingestion_utils import extract_text
from database.postgres_service import insert_embedding, update_file_status

_embeddings = OllamaEmbeddings(model="nomic-embed-text")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


def embed_text(text: str) -> List[float]:
    return _embeddings.embed_documents([text])[0]


def process_document(file_path: str) -> List[Dict]:
    """
    Full ingestion pipeline:
    file → text → chunks → embeddings
    """

    # 1. Extract text
    text = extract_text(file_path)

    # 2. Split into chunks
    chunks = chunk_text(text)

    # 3. Generate embeddings
    result = []

    for chunk in chunks:
        result.append({
            "content": chunk,
            "embedding": embed_text(chunk)
        })

    return result

def ingest_and_store(file_path: str, file_id: int) -> None:
    try:
        text = extract_text(file_path)
        chunks = chunk_text(text)

        for index, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            insert_embedding(
                document_id=file_id,
                content=chunk,
                embedding=embedding,
                chunk_index=index
            )

        update_file_status(file_id, "done")
    except Exception as e:
        update_file_status(file_id, "failed")
        raise e