from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil

router = APIRouter()

UPLOAD_DIR = "../storage/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def is_allowed_file(file: UploadFile) -> bool:
    allowed_content_types = [
        "text/plain",
        "application/pdf"
    ]

    allowed_extensions = [".txt", ".pdf"]

    if file.content_type not in allowed_content_types:
        return False

    if not any(file.filename.endswith(ext) for ext in allowed_extensions):
        return False

    return True


@router.post("/upload")
def upload(file: UploadFile = File(...)):

    if not is_allowed_file(file):
        raise HTTPException(
            status_code=400,
            detail="Only .txt files are allowed"
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "file uploaded successfully",
        "filename": file.filename,
        "path": file_path
    }