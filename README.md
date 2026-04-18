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

- **Document ingestion** — upload PDF and text files; they are chunked, embedded, and stored in PostgreSQL
- **Chat** — conversational interface backed by RAG; the LLM answers using retrieved context
- **Search** — three search modes available:
  - **Semantic** — vector cosine similarity via pgvector
  - **Keyword** — PostgreSQL full-text search (`plainto_tsquery`)
  - **Hybrid** — combines both using Reciprocal Rank Fusion (RRF)
- **Model management** — add and switch between LLM backends (Ollama, OpenAI, Anthropic, custom OpenAI-compatible)
- **Document viewer** — browse uploaded files and inspect their chunks
- **Fully local** — no telemetry, no external APIs required (unless you configure OpenAI / Anthropic models)

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
                                                       │  │ LLM Router     │  │
                                                       │  │ (Ollama /      │  │
                                                       │  │  OpenAI /      │  │
                                                       │  │  Anthropic /   │  │
                                                       │  │  Custom)       │  │
                                                       │  └────────────────┘  │
                                                       └──────────────────────┘
```

---

## Project Structure

```
Local-RAG-Service/
├── backend/
│   ├── main.py                         # FastAPI app entry point
│   ├── requirements.txt
│   ├── api/
│   │   └── routes/
│   │       ├── chat.py                 # POST /chat  — RAG + LLM
│   │       ├── retrieval.py            # POST /search
│   │       ├── documents.py            # CRUD /documents
│   │       └── models.py               # CRUD /models
│   ├── llm/                            # One service file per LLM provider
│   │   ├── __init__.py                 # Re-exports all call() functions
│   │   ├── ollama.py                   # Ollama  → /api/generate
│   │   ├── openai.py                   # OpenAI  → /v1/chat/completions
│   │   ├── anthropic.py                # Anthropic → /v1/messages
│   │   └── custom.py                   # Custom OpenAI-compatible endpoint
│   └── database/
│       ├── postgres_service.py         # Connection pool, schema, queries
│       ├── embeddings.py               # fastembed singleton (BAAI/bge-small-en-v1.5)
│       ├── ingestion/
│       │   └── ingestion_service.py    # PDF parsing + chunking + embedding
│       └── retrieval/
│           └── retrieval_service.py    # Semantic / keyword / hybrid search
└── frontend/
    └── src/app/
        ├── pages/
        │   ├── chat/                   # Chat page
        │   ├── search/                 # Search page (3 modes)
        │   ├── documents/              # Document list & viewer
        │   ├── upload/                 # File upload with progress
        │   └── models/                 # Model CRUD
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
| Ollama | `llama3.2` | `http://localhost:11434` | — |
| OpenAI | `gpt-4o` | — | your key |
| Anthropic | `claude-3-5-sonnet-20241022` | — | your key |
| Custom | model name | endpoint URL | if required |

4. Click the ★ to set a default, then open **Chat** and start talking.

---

## Embedding Model

Documents are embedded with **[BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)** via `fastembed` (384-dimensional vectors). The model is downloaded automatically on first run and cached locally.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload and ingest a document |
| `GET` | `/documents` | List all documents |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `POST` | `/search` | Search chunks (semantic / keyword / hybrid) |
| `POST` | `/chat` | RAG chat with an LLM |
| `GET` | `/models` | List configured models |
| `POST` | `/models` | Add a model |
| `PUT` | `/models/{id}` | Update a model |
| `PATCH` | `/models/{id}/default` | Set default model |
| `DELETE` | `/models/{id}` | Delete a model |

---

