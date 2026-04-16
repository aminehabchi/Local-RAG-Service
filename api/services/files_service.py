import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile

# =========================
# CONFIG
# =========================

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "txt"}

# =========================
# HELPERS
# =========================

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = filename.split(".")[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def generate_filename(original_filename: str) -> str:
    """Generate a safe unique filename using UUID."""
    ext = original_filename.split(".")[-1].lower()
    return f"{uuid.uuid4()}.{ext}"


# =========================
# CORE FILE OPERATIONS
# =========================

async def save_file(file: UploadFile, folder: Optional[str] = None) -> str:
    """
    Save uploaded file to disk.
    Returns saved file path.
    """
    if not is_allowed_file(file.filename):
        raise ValueError("File type not allowed")

    target_dir = UPLOAD_DIR

    if folder:
        target_dir = UPLOAD_DIR / folder
        target_dir.mkdir(parents=True, exist_ok=True)

    filename = generate_filename(file.filename)
    file_path = target_dir / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return str(file_path)


def delete_file(file_path: str) -> bool:
    """Delete a file if it exists."""
    path = Path(file_path)

    if path.exists() and path.is_file():
        path.unlink()
        return True

    return False


def get_file_info(file_path: str) -> dict:
    """Get metadata about a file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError("File not found")

    return {
        "name": path.name,
        "size": path.stat().st_size,
        "extension": path.suffix,
        "created_at": path.stat().st_ctime,
    }


def list_files(folder: Optional[str] = None) -> List[str]:
    """List all files in upload directory or subfolder."""
    target_dir = UPLOAD_DIR

    if folder:
        target_dir = UPLOAD_DIR / folder

    if not target_dir.exists():
        return []

    return [str(f) for f in target_dir.iterdir() if f.is_file()]