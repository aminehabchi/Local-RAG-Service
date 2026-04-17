from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.sqlite_service import get_all_files, get_file_by_name, delete_file as db_delete_file, get_file_by_id
from services.files_service import delete_file as fs_delete_file
import mimetypes

router = APIRouter()


@router.get("/documents")
def list_documents():
    return get_all_files()


@router.get("/documents/{file_id}/view")
def view_document(file_id: int):
    doc = get_file_by_id(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    mime_type, _ = mimetypes.guess_type(doc["path"])
    return FileResponse(
        path=doc["path"],
        media_type=mime_type or "application/octet-stream",
        headers={"Content-Disposition": "inline"},
    )


@router.delete("/documents/{file_id}")
def delete_document(file_id: int):
    doc = get_file_by_id(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fs_delete_file(doc["path"])
    db_delete_file(file_id)
    return {"message": "Document deleted successfully"}
