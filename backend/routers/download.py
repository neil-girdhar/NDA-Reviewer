from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
import io

from database import get_session
from models import Document, Review, ClauseFinding
from services.redline_service import generate_issues_report, generate_clean_copy, generate_negotiation_pack

router = APIRouter(prefix="/api", tags=["download"])


def _get_review_doc_findings(review_id: str, session: Session):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    doc = session.get(Document, review.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Original document not found.")
    findings = session.exec(
        select(ClauseFinding).where(ClauseFinding.review_id == review_id)
    ).all()
    return review, doc, [f.model_dump() for f in findings]


@router.get("/download/{review_id}/report")
def download_issues_report(review_id: str, session: Session = Depends(get_session)):
    """
    Download 1: Red + Amber issues in contract order — original text struck out,
    replacement in green, risk reason below each.
    """
    review, doc, findings = _get_review_doc_findings(review_id, session)
    try:
        docx_bytes = generate_issues_report(
            doc.file_bytes, doc.filename, findings, raw_text=doc.raw_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate issues report: {e}")

    safe_name = doc.filename.rsplit(".", 1)[0] + "_issues_report.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/download/{review_id}/negotiation")
def download_negotiation_pack(review_id: str, session: Session = Depends(get_session)):
    """
    Download 2: Redlines + talking points in one document — for BD / PM use
    when pushing back on the counterparty.
    """
    review, doc, findings = _get_review_doc_findings(review_id, session)
    try:
        docx_bytes = generate_negotiation_pack(
            doc.file_bytes, doc.filename, findings, raw_text=doc.raw_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate negotiation pack: {e}")

    safe_name = doc.filename.rsplit(".", 1)[0] + "_negotiation_pack.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/download/{review_id}/clean")
def download_clean_copy(review_id: str, session: Session = Depends(get_session)):
    """
    Download 3: Full NDA with all Red + Amber changes applied.
    Green clauses unchanged. Purple changes require Gigi's final review.
    """
    review, doc, findings = _get_review_doc_findings(review_id, session)
    try:
        docx_bytes = generate_clean_copy(
            doc.file_bytes, doc.filename, findings, raw_text=doc.raw_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clean copy: {e}")

    safe_name = doc.filename.rsplit(".", 1)[0] + "_clean_copy.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


# Legacy endpoint
@router.get("/download/{review_id}/docx")
def download_redline_legacy(review_id: str, session: Session = Depends(get_session)):
    return download_issues_report(review_id, session)
