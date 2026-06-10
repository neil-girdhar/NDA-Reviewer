from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from database import get_session
from models import Document, Review, ClauseFinding, ReviewRead, ReviewSummary, ClauseFindingRead
from services.parser import segment_clauses, segment_clauses_docx
from services.claude_service import analyse_nda
from services import storage_service

router = APIRouter(prefix="/api", tags=["review"])


class ReviewRequest(BaseModel):
    document_id: str
    # high_stakes flag removed — all reviews now use Opus 4.8 + adaptive thinking


class SaveRequest(BaseModel):
    saved: bool


@router.post("/review", response_model=ReviewRead)
def create_review(
    req: ReviewRequest,
    session: Session = Depends(get_session),
):
    doc = session.get(Document, req.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.filename.lower().endswith(".docx"):
        clauses = segment_clauses_docx(doc.file_bytes)
    else:
        clauses = segment_clauses(doc.raw_text)
    if not clauses:
        raise HTTPException(status_code=422, detail="Could not segment clauses from document.")

    try:
        raw_findings = analyse_nda(doc.raw_text, clauses)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude analysis failed: {e}")

    if not isinstance(raw_findings, list) or not raw_findings:
        raise HTTPException(
            status_code=502,
            detail="Claude returned no findings — the NDA may be too large or the response was truncated. Try again.",
        )

    rag_order = {"Red": 0, "Amber": 1, "Green": 2}
    try:
        overall = min(raw_findings, key=lambda f: rag_order.get(f.get("rag_rating", "Green"), 2))
        overall_risk = overall.get("rag_rating", "Green")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process findings: {e}")

    from config import settings
    model_used = settings.high_stakes_model   # always Opus 4.8

    review = Review(
        document_id=doc.id,
        overall_risk=overall_risk,
        model_used=model_used,
        saved=False,
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    def _str(val, default="") -> str:
        """Coerce a Claude response value to str — handles the case where
        Claude returns a list for talking_points or other string fields."""
        if val is None:
            return default
        if isinstance(val, list):
            return "\n".join(str(item) for item in val)
        return str(val)

    finding_records = []
    for f in raw_findings:
        cf = ClauseFinding(
            review_id=review.id,
            clause_type=_str(f.get("clause_type"), "Unknown"),
            original_text=_str(f.get("original_text")),
            rag_rating=_str(f.get("rag_rating"), "Green"),
            plain_english_summary=_str(f.get("plain_english_summary")),
            risk_reason=_str(f.get("risk_reason")),
            suggested_redline=_str(f.get("suggested_redline")),
            replacement_language=_str(f.get("replacement_language")),
            talking_points=_str(f.get("negotiation_talking_points")),
        )
        session.add(cf)
        finding_records.append(cf)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        # Clean up the orphaned review record before surfacing the error
        session.delete(review)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save findings: {e}")
    session.refresh(review)
    for cf in finding_records:
        session.refresh(cf)

    return ReviewRead(
        **review.model_dump(),
        filename=doc.filename,
        findings=[ClauseFindingRead(**cf.model_dump()) for cf in finding_records],
    )


@router.get("/review/{review_id}", response_model=ReviewRead)
def get_review(review_id: str, session: Session = Depends(get_session)):
    result = storage_service.get_review(session, review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Review not found.")
    return result


@router.put("/review/{review_id}/save")
def toggle_save(review_id: str, req: SaveRequest, session: Session = Depends(get_session)):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    review.saved = req.saved
    session.add(review)
    session.commit()
    return {"id": review_id, "saved": review.saved}


@router.get("/reviews", response_model=list[ReviewSummary])
def list_reviews(session: Session = Depends(get_session)):
    return storage_service.list_saved_reviews(session)


class FindingUpdate(BaseModel):
    suggested_redline: Optional[str] = None
    replacement_language: Optional[str] = None
    talking_points: Optional[str] = None


@router.get("/finding/{finding_id}", response_model=ClauseFindingRead)
def get_finding(
    finding_id: str,
    session: Session = Depends(get_session),
):
    """Read the current DB state of a single finding — useful for verifying that
    inline edits were saved correctly before downloading."""
    cf = session.get(ClauseFinding, finding_id)
    if not cf:
        raise HTTPException(status_code=404, detail="Finding not found.")
    return ClauseFindingRead(**cf.model_dump())


@router.patch("/finding/{finding_id}", response_model=ClauseFindingRead)
def update_finding(
    finding_id: str,
    req: FindingUpdate,
    session: Session = Depends(get_session),
):
    """Persist inline edits to a clause finding (redline text, replacement, talking points)."""
    cf = session.get(ClauseFinding, finding_id)
    if not cf:
        raise HTTPException(status_code=404, detail="Finding not found.")
    if req.suggested_redline is not None:
        cf.suggested_redline = req.suggested_redline
    if req.replacement_language is not None:
        cf.replacement_language = req.replacement_language
    if req.talking_points is not None:
        cf.talking_points = req.talking_points
    session.add(cf)
    session.commit()
    session.refresh(cf)
    return ClauseFindingRead(**cf.model_dump())


@router.delete("/review/{review_id}")
def delete_review(review_id: str, session: Session = Depends(get_session)):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    session.delete(review)
    session.commit()
    return {"deleted": review_id}
