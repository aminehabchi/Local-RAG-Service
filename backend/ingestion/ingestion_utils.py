import re
from pathlib import Path
import fitz


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)          # collapse whitespace
    text = re.sub(r'[^\x20-\x7E\n]', '', text) # drop non-printable chars
    return text.strip()


def read_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    pages = []

    for page in doc:
        pages.append(page.get_text())

    doc.close()
    return "\n".join(pages)


def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()

    if ext == ".txt":
        raw = read_txt(file_path)
    elif ext == ".pdf":
        raw = read_pdf(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return clean_text(raw)
