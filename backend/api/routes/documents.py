import mimetypes
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from database.postgres_service import get_all_files, get_file_by_id, insert_file, delete_file_db
from storage.files_service import delete_file_fs, is_allowed_file, generate_filename, save_file_fs
from ingestion.ingestion_service import ingest_and_store


router = APIRouter()


# =========================
# GET ALL DOCUMENTS
# =========================
@router.get("/documents")
async def list_documents():
    return get_all_files()


# =========================
# VIEW DOCUMENT
# =========================
@router.get("/documents/{file_id}/view")
async def view_document(file_id: int):
    doc = get_file_by_id(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    mime_type, _ = mimetypes.guess_type(doc["path"])

    return FileResponse(
        path=doc["path"],
        media_type=mime_type or "application/octet-stream",
        headers={"Content-Disposition": "inline"},
    )


# =========================
# DELETE DOCUMENT
# =========================
@router.delete("/documents/{file_id}")
async def delete_document(file_id: int):
    doc = get_file_by_id(file_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_file_fs(doc["path"])
    delete_file_db(file_id)

    return {"message": "Document deleted successfully"}


# =========================
# UPLOAD FILE
# =========================
@router.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Only .pdf and .txt files are allowed"
            )

        hashed_name = generate_filename(file.filename)
        file_path = await save_file_fs(file, hashed_name)
        file_size = Path(file_path).stat().st_size

        file_id = insert_file(
            original_name=file.filename,
            hashed_name=hashed_name,
            path=file_path,
            size=file_size
        )

        background_tasks.add_task(ingest_and_store, file_path, file_id)

        return {
            "message": "file uploaded successfully",
            "file_id": file_id,
            "original_name": file.filename,
            "hashed_name": hashed_name,
            "path": file_path
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
