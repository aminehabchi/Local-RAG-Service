# Local RAG Service

A fully local Retrieval-Augmented Generation (RAG) system. Upload your documents, let the system index and embed them, then chat with your knowledge base — all running on your own machine with no data leaving your environment.

---

## Technologies & Libraries Used

### Database
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgAdmin](https://img.shields.io/badge/pgAdmin-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.pgadmin.org/)
[![pgvector](https://img.shields.io/badge/pgvector-000000?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)

### Backend
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com/)
[![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)](https://numpy.org/)

### Frontend
[![Angular](https://img.shields.io/badge/Angular_21-DD0031?style=for-the-badge&logo=angular&logoColor=white)](https://angular.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![RxJS](https://img.shields.io/badge/RxJS-B7178C?style=for-the-badge&logo=reactivex&logoColor=white)](https://rxjs.dev/)
[![SCSS](https://img.shields.io/badge/SCSS-CC6699?style=for-the-badge&logo=sass&logoColor=white)](https://sass-lang.com/)

---

## Features

- **Document ingestion** — upload PDF and TXT files; they are cleaned, chunked, embedded, and stored in PostgreSQL
- **Reindexing** — re-ingest any document from scratch without re-uploading
- **Chat** — conversational interface backed by RAG; the LLM answers using retrieved context
- **Search** — three search modes:
  - **Semantic** — vector cosine similarity via pgvector
  - **Keyword** — PostgreSQL full-text search (`plainto_tsquery`)
  - **Hybrid** — combines both using Reciprocal Rank Fusion (RRF)
- **Model management** — add and switch between LLM backends (Ollama, OpenAI, Anthropic, Gemini)
- **Document viewer** — browse uploaded files, inspect chunks, and view PDFs inline
- **Fully local** — no telemetry, no external APIs required (unless you configure cloud models)

---

## Architecture

```
┌─────────────────────┐        HTTP (port 8000)       ┌──────────────────────┐
│   Angular Frontend  │ ◄────────────────────────────► │   FastAPI Backend    │
│     (port 4200)     │                                │                      │
└─────────────────────┘                                │  ┌────────────────┐  │
                                                       │  │ Ingestion      │  │
                                                       │  │ (PyMuPDF +     │  │
                                                       │  │  fastembed)    │  │
                                                       │  └───────┬────────┘  │
                                                       │          │           │
                                                       │  ┌───────▼────────┐  │
                                                       │  │  PostgreSQL    │  │
                                                       │  │  + pgvector    │  │
                                                       │  └───────┬────────┘  │
                                                       │          │           │
                                                       │  ┌───────▼────────┐  │
                                                       │  │ Retrieval      │  │
                                                       │  │ (semantic /    │  │
                                                       │  │  keyword /     │  │
                                                       │  │  hybrid)       │  │
                                                       │  └───────┬────────┘  │
                                                       │          │           │
                                                       │  ┌───────▼────────┐  │
                                                       │  │ LLM Factory    │  │
                                                       │  │ (Ollama /      │  │
                                                       │  │  OpenAI /      │  │
                                                       │  │  Anthropic /   │  │
                                                       │  │  Gemini)       │  │
                                                       │  └────────────────┘  │
                                                       └──────────────────────┘
```

---

## Project Structure

```
Local-RAG-Service/
├── backend/
│   ├── main.py                             # FastAPI app entry point
│   ├── requirements.txt
│   ├── api/
│   │   └── routes/
│   │       ├── chat.py                     # POST /chat  — RAG + LLM
│   │       ├── retrieval.py                # POST /search
│   │       ├── documents.py                # CRUD /documents
│   │       └── models.py                   # CRUD /models
│   ├── llm/
│   │   ├── base.py                         # Abstract LLMProvider
│   │   ├── __init__.py                     # get_provider() factory
│   │   ├── ollama.py                       # OllamaProvider
│   │   ├── openai.py                       # OpenAIProvider
│   │   ├── anthropic.py                    # AnthropicProvider
│   │   └── gemini.py                       # GeminiProvider
│   └── database/
│       ├── postgres_service.py             # Connection pool, schema, queries
│       ├── embedding/
│       │   └── embeddings_model.py         # fastembed singleton (BAAI/bge-small-en-v1.5)
│       ├── ingestion/
│       │   ├── ingestion_service.py        # Orchestrates the full ingestion pipeline
│       │   ├── cleaning.py                 # Text normalisation
│       │   ├── chunking.py                 # Text splitting
│       │   └── embedding_inserting.py      # Embeds chunks and writes to DB
│       └── retrieval/
│           ├── retrieval_service.py        # Orchestrates search
│           ├── cleaning.py                 # Query normalisation
│           └── search.py                   # Semantic / keyword / hybrid queries
└── frontend/
    └── src/app/
        ├── pages/
        │   ├── home/                       # Landing page
        │   ├── chat/                       # Chat page
        │   ├── search/                     # Search page (3 modes)
        │   ├── documents/                  # Document list, viewer & chunk inspector
        │   ├── upload/                     # File upload with live progress
        │   └── models/                     # Model CRUD
        └── services/
            ├── chat.ts
            ├── search.ts
            ├── upload.ts
            └── models.ts
```

---

## Getting Started

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| PostgreSQL | 15+ with pgvector extension |
| Ollama *(optional)* | latest |

### 1 — PostgreSQL setup

```sql
CREATE DATABASE rag_db;
-- Connect to rag_db, then:
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2 — Backend

```bash
cd backend
python -m venv rag-env
source rag-env/bin/activate        # Windows: rag-env\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3 — Frontend

```bash
cd frontend
npm install
ng serve                            # opens http://localhost:4200
```

### 4 — Add a model

1. Open **http://localhost:4200**
2. Go to **Models** in the sidebar
3. Click **Add Model** and fill in the details:

| Type | Name field | Base URL | API Key |
|---|---|---|---|
| Local / Ollama | `llama3.2` | `http://localhost:11434` | — |
| OpenAI | `gpt-4o` | — | your key |
| Anthropic | `claude-3-5-sonnet-20241022` | — | your key |
| Gemini | `gemini-2.5-flash` | — | your key |

4. Click the ★ to set a default, then open **Chat** and start talking.

---

## Embedding Model

Documents are embedded with **[BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)** via `fastembed` (384-dimensional vectors). The model is downloaded automatically on first run and cached at `~/.cache/fastembed/` — subsequent runs load it instantly from disk.

---

## LLM Provider Factory

The `llm/` package uses a **factory pattern**. Each provider is a class that inherits from `LLMProvider` and implements a single `chat(messages)` method. `get_provider(model)` resolves the correct class at runtime based on the model type stored in the database.

Adding a new provider requires only two steps: create a new class in `llm/` and register it in `_REGISTRY` inside `llm/__init__.py`.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload and ingest a document |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}/chunks` | List chunks for a document |
| `GET` | `/documents/{id}/view` | Stream the original file |
| `POST` | `/documents/{id}/reindex` | Re-ingest a document from scratch |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `POST` | `/search` | Search chunks (semantic / keyword / hybrid) |
| `POST` | `/chat` | RAG chat with an LLM |
| `GET` | `/models` | List configured models |
| `POST` | `/models` | Add a model |
| `PUT` | `/models/{id}` | Update a model |
| `PATCH` | `/models/{id}/default` | Set default model |
| `DELETE` | `/models/{id}` | Delete a model |

---
