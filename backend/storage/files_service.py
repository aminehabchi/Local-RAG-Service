import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile

# =========================
# CONFIG
# =========================

UPLOAD_DIR = Path(__file__).parent / "documents"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "txt"}

# =========================
# HELPERS
# =========================

def is_allowed_file(filename: str) -> bool:
    ext = filename.split(".")[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def generate_filename(original_filename: str) -> str:
    ext = original_filename.split(".")[-1].lower()
    return f"{uuid.uuid4()}.{ext}"


# =========================
# CORE SERVICE
# =========================

async def save_file_fs(file: UploadFile, hashed_name: str, folder: Optional[str] = None) -> str:
    """
    Save file using a pre-generated hashed filename.
    Returns saved file path.
    """

    target_dir = UPLOAD_DIR

    if folder:
        target_dir = UPLOAD_DIR / folder
        target_dir.mkdir(parents=True, exist_ok=True)

    # use provided hashed name instead of generating it here
    file_path = target_dir / hashed_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return str(file_path)


def delete_file_fs(file_path: str) -> bool:
    path = Path(file_path)

    if path.exists() and path.is_file():
        path.unlink()
        return True

    return False


def get_file_info_fs(file_path: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError("File not found")

    return {
        "name": path.name,
        "size": path.stat().st_size,
        "extension": path.suffix,
        "created_at": path.stat().st_ctime,
    }


def list_files_fs(folder: Optional[str] = None) -> List[str]:
    target_dir = UPLOAD_DIR / folder if folder else UPLOAD_DIR

    if not target_dir.exists():
        return []

    return [str(f) for f in target_dir.iterdir() if f.is_file()]