# Local RAG Service

A fully local Retrieval-Augmented Generation (RAG) service that lets you upload documents and query them using natural language. No data leaves your machine — everything runs on your own hardware.

---

## What it does

You upload a document (PDF, DOCX, TXT). The service breaks it into chunks, converts each chunk into a vector embedding, and stores those vectors locally in Qdrant. When you ask a question, the same embedding model converts your question into a vector, finds the most semantically similar chunks, and feeds them as context to a local LLM (via Ollama) which generates a grounded answer with source citations.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  UI Layer       Next.js / Streamlit / Gradio         │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  API Layer      FastAPI  +  Pydantic v2              │
│                 POST /upload   POST /query            │
└──────────┬─────────────────────────────┬────────────┘
           │                             │
┌──────────▼──────────┐   ┌─────────────▼────────────┐
│  Ingestion Pipeline │   │  Query Pipeline           │
│                     │   │                           │
│  1. Parse file      │   │  1. Embed question        │
│  2. Split chunks    │   │  2. Vector search         │
│  3. Embed chunks    │   │  3. Filter by doc_id      │
│  4. Upsert Qdrant   │   │  4. Build prompt          │
│  5. Save metadata   │   │  5. LLM generates answer  │
└──────────┬──────────┘   └─────────────┬────────────┘
           │                             │
┌──────────▼─────────────────────────────▼────────────┐
│  Storage Layer                                       │
│                                                      │
│  Qdrant (vectors + payloads)                         │
│  SQLite / SQLAlchemy (document metadata)             │
│  Local filesystem  (original files)                  │
└──────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  LLM Layer      Ollama  (Llama 3 / Mistral / Phi-3)  │
│                 100% local — no API calls            │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI | REST endpoints, file upload, SSE streaming |
| Validation | Pydantic v2 | Request/response models |
| Parsing | PyMuPDF, python-docx | Extract text from PDF, DOCX, TXT |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | Split text into overlapping passages |
| Embedding | `sentence-transformers` (nomic-embed-text) | Convert text to vectors |
| Vector DB | Qdrant | Store and search vectors |
| Metadata DB | SQLite + SQLAlchemy | Track documents, status, chunk counts |
| LLM runner | Ollama | Run local language models |
| Models | Llama 3 / Mistral / Phi-3 | Generate answers from retrieved context |
| UI | Streamlit (quick) or Next.js (production) | User interface |

---

## Project Structure

```
rag-service/
├── api/
│   ├── main.py            # FastAPI app, route registration
│   ├── routes/
│   │   ├── upload.py      # POST /upload
│   │   └── query.py       # POST /query
│   └── models.py          # Pydantic request/response schemas
│
├── ingestion/
│   ├── parser.py          # File → raw text (PDF, DOCX, TXT)
│   ├── chunker.py         # Text → overlapping chunks
│   └── embedder.py        # Chunks → vectors (sentence-transformers)
│
├── storage/
│   ├── qdrant.py          # Qdrant client wrapper (upsert, search, delete)
│   └── database.py        # SQLite models + SQLAlchemy session
│
├── retrieval/
│   ├── search.py          # Query embedding + Qdrant search
│   └── prompt.py          # Build augmented prompt from chunks
│
├── llm/
│   └── ollama.py          # Ollama client, streaming response
│
├── data/
│   ├── docs/              # Uploaded original files
│   └── qdrant_data/       # Qdrant persistent storage
│
├── requirements.txt
├── docker-compose.yml     # Qdrant + app services
└── README.md
```

---

## Ingestion Pipeline

When a user uploads a file, the following happens in order:

1. **Receive** — FastAPI accepts the file via `POST /upload` (multipart/form-data)
2. **Save to disk** — original file saved to `data/docs/{uuid}_{filename}`
3. **Record metadata** — a row is written to SQLite with `status = "processing"`
4. **Extract text** — file parsed into plain text using PyMuPDF or python-docx
5. **Chunk** — text split into ~512-token passages with 50-token overlap
6. **Embed** — each chunk passed through the embedding model → 768-dim vector
7. **Upsert** — vectors + payload stored in Qdrant
8. **Update status** — SQLite row updated to `status = "ready"`, `chunk_count = N`
9. **Respond** — API returns `{ doc_id, chunks, status: "ready" }`

Each Qdrant point stores:

```python
{
  "id":          "uuid",
  "vector":      [0.02, -0.81, ...],   # 768 floats
  "payload": {
    "text":        "The refund window is 30 days.",
    "doc_id":      "abc-123",
    "chunk_index": 4,
    "filename":    "policy.pdf",
    "page":        2,
  }
}
```

---

## Query Pipeline

When a user submits a question:

1. **Embed** the question using the same model used at ingestion time
2. **Search** Qdrant for the top-5 most similar chunks (cosine similarity)
3. **Filter** optionally restrict to a specific `doc_id`
4. **Build prompt** — inject retrieved chunks as context into the LLM prompt
5. **Generate** — Ollama streams the answer token by token
6. **Return** — response includes the answer text + source citations

---

## Qdrant Components

| Component | What it is | Used for |
|---|---|---|
| `QdrantClient` | Connection object | All operations go through this |
| `Collection` | Named vector bucket | One collection called `"documents"` |
| `PointStruct` | Single stored item | One chunk = one point |
| `payload` | Metadata dict on each point | Stores text, doc_id, filename, page |
| `upsert()` | Insert or update points | Storing chunks after ingestion |
| `search()` | Find similar vectors | Finding relevant chunks at query time |
| `Filter` | Narrow search scope | Search within one document only |
| `delete()` | Remove points | Clean up when a document is deleted |

---

## Installation

### Prerequisites

- Python 3.11+
- Docker (for Qdrant)
- [Ollama](https://ollama.com) installed and running

### 1. Clone and install

```bash
git clone https://github.com/yourname/rag-service
cd rag-service
pip install -r requirements.txt
```

### 2. Start Qdrant

```bash
docker run -d -p 6333:6333 -v ./data/qdrant_data:/qdrant/storage qdrant/qdrant
```

### 3. Pull a local model

```bash
ollama pull llama3
# or: ollama pull mistral
# or: ollama pull phi3
```

### 4. Run the API

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Open the UI

```bash
streamlit run ui/app.py
```

---

## Requirements

```
fastapi
uvicorn
python-multipart
langchain
langchain-community
sentence-transformers
qdrant-client
sqlalchemy
ollama
pymupdf
python-docx
streamlit
```

---

## Key Design Decisions

**Why Qdrant over Chroma?** Qdrant runs as a persistent Docker container, supports payload filtering, and is production-ready. Chroma is simpler to start but harder to scale.

**Why the same embedding model for ingestion and query?** Each model defines its own vector space. Using different models at ingestion vs query time produces incompatible vectors — similarity scores become meaningless.

**Why store `text` in the Qdrant payload?** So the query pipeline never needs to touch disk. The retrieved chunk text travels with the vector and is immediately available to inject into the LLM prompt.

**Why keep original files on disk?** So you can re-process them if you change chunking strategy, swap embedding models, or want to extract additional metadata later.

**Why SQLite alongside Qdrant?** Qdrant stores vectors and their payloads but isn't suited for relational queries like "list all documents uploaded today" or "show documents with status=processing". SQLite handles that cleanly.

---

## API Reference

### `POST /upload`

Upload a document for ingestion.

**Request:** `multipart/form-data` with file field

**Response:**
```json
{
  "doc_id": "abc-123",
  "filename": "policy.pdf",
  "chunk_count": 40,
  "status": "ready"
}
```

---

### `POST /query`

Ask a question against the stored documents.

**Request:**
```json
{
  "question": "What is the refund policy?",
  "doc_id": "abc-123",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Refunds are accepted within 30 days of purchase...",
  "sources": [
    { "filename": "policy.pdf", "page": 2, "chunk_index": 4, "score": 0.91 }
  ]
}
```

