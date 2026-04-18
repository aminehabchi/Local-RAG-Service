from typing import List
from fastembed import TextEmbedding
from ingestion.ingestion_utils import extract_text
from database.postgres_service import create_connection, update_file_status, update_file_chunk_count
import re

_embeddings = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'\n+', '\n', text)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:%()\-\']', '', text)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if len(chunk.strip()) > 30:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def ingest_and_store(file_path: str, file_id: int) -> None:
    try:
        text = extract_text(file_path)
        text = clean_text(text)

        chunks = chunk_text(text)
        update_file_chunk_count(file_id, len(chunks))

        conn = create_connection()
        if not conn:
            raise RuntimeError("Failed to connect to database")

        cursor = conn.cursor()
        print(f"Extracted {len(chunks)} chunks from document {file_id}")
        for index, chunk in enumerate(chunks):
            print(index)
            clean_chunk = clean_text(chunk)

            embedding = list(_embeddings.embed([clean_chunk]))[0].tolist()

            cursor.execute(
                """
                INSERT INTO document_chunks (file_id, content, embedding, chunk_index)
                VALUES (%s, %s, %s, %s)
                """,
                (file_id, clean_chunk, str(embedding), index)
            )

        conn.commit()
        conn.close()

        update_file_status(file_id, "done")

    except Exception as e:
        update_file_status(file_id, "failed")
        raise e