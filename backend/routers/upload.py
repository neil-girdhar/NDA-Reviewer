from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from config import settings
from database import get_session
from models import Document
from services.parser import extract_text

router = APIRouter(prefix="/api", tags=["upload"])

_ALLOWED_EXTENSIONS = {"pdf", "docx"}


@router.post("/upload")
async def upload_nda(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported.")

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit.")

    try:
        raw_text = extract_text(file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract text: {e}")

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in document.")

    doc = Document(filename=file.filename, raw_text=raw_text, file_bytes=file_bytes)
    session.add(doc)
    session.commit()
    session.refresh(doc)

    return {"document_id": doc.id, "filename": doc.filename, "char_count": len(raw_text)}
