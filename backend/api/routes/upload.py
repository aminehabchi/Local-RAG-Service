from services.files_service import generate_filename, is_allowed_file, save_file
from services.sqlite_service import insert_file
from fastapi import APIRouter, UploadFile, File, HTTPException


router = APIRouter()


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        # 1. Validate file
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Only .pdf and .txt files are allowed"
            )

        # 2. Generate hashed filename (single source of truth)
        hashed_name = generate_filename(file.filename)

        # 3. Save file with hashed name
        file_path = await save_file(file, hashed_name)

        # 4. Store in DB
        insert_file(
            original_name=file.filename,
            hashed_name=hashed_name,
            path=file_path
        )

        return {
            "message": "file uploaded successfully",
            "original_name": file.filename,
            "hashed_name": hashed_name,
            "path": file_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))