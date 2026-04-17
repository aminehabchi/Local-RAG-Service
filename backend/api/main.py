from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.documents import router as documents_router
from services.postgres_service import init_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(documents_router)