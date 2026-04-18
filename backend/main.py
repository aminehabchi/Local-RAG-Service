from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.documents import router as documents_router
from api.routes.retrieval import router as retrieval_router
from api.routes.models import router as models_router
from api.routes.chat import router as chat_router
from database.postgres_service import init_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(models_router)
app.include_router(chat_router)
