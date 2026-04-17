from typing import List, Dict
from ingestion.ingestion_utils import extract_text
from database.postgres_service import insert_embedding

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return chunks


def embed_text(text: str) -> List[float]:
    """
    Replace later with OpenAI / Ollama embeddings
    """
    import random
    return [random.random() for _ in range(384)]


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
    """
    Full pipeline:
    file → text → chunks → embeddings → store in DB
    """

    # 1. Extract text from file
    text = extract_text(file_path)

    # 2. Split into chunks
    chunks = chunk_text(text)

    # 3. Process each chunk
    for index, chunk in enumerate(chunks):
        embedding = embed_text(chunk)

        # 4. Store in database
        insert_embedding(
            document_id=file_id,
            content=chunk,
            embedding=embedding,
            chunk_index=index
        )