from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.documents import router as documents_router
from api.routes.retrieval import router as retrieval_router
from api.routes.models import router as models_router
from api.routes.chat import router as chat_router
from database.postgres_service import init_db, fail_processing_files
from database.embedding.embeddings_model import get_embeddings_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    fail_processing_files()  # recover from previous crash
    get_embeddings_model()  # pre-warm so first request doesn't pay the load cost
    yield
    fail_processing_files()  # mark in-flight uploads as failed on shutdown


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(models_router)
app.include_router(chat_router)
