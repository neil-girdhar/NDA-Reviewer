from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
import io

from database import get_session
from models import Document, Review, ClauseFinding
from services.redline_service import generate_issues_report, generate_clean_copy

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
def download_issues_report(
    review_id: str,
    findings: str = "",
    session: Session = Depends(get_session)
):
    """
    Download 1: Inline redline of the original NDA showing selected Red/Amber changes.

    Original problematic text shown in RED STRIKETHROUGH, replacement in GREEN.

    Query param 'findings' is a comma-separated list of finding IDs to apply.
    If empty or not provided, applies all Red/Amber findings.
    """
    review, doc, all_findings = _get_review_doc_findings(review_id, session)

    # Filter findings based on selected IDs
    if findings:
        selected_ids = {str(fid).strip() for fid in findings.split(',') if str(fid).strip()}
        filtered_findings = [f for f in all_findings if str(f['id']) in selected_ids]
    else:
        # Default: apply all Red and Amber findings
        filtered_findings = [f for f in all_findings if f['rag_rating'] in ('Red', 'Amber')]

    try:
        docx_bytes = generate_issues_report(
            doc.file_bytes, doc.filename, filtered_findings, raw_text=doc.raw_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate issues report: {e}")

    safe_name = doc.filename.rsplit(".", 1)[0] + "_redline.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store",
        },
    )


# Negotiation pack removed - talking points no longer generated
# @router.get("/download/{review_id}/negotiation")
# def download_negotiation_pack(review_id: str, session: Session = Depends(get_session)):
#     """
#     Download 2: Redlines + talking points in one document — for BD / PM use
#     when pushing back on the counterparty.
#     """
#     review, doc, findings = _get_review_doc_findings(review_id, session)
#     try:
#         docx_bytes = generate_negotiation_pack(
#             doc.file_bytes, doc.filename, findings, raw_text=doc.raw_text
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to generate negotiation pack: {e}")
#
#     safe_name = doc.filename.rsplit(".", 1)[0] + "_negotiation_pack.docx"
#     return StreamingResponse(
#         io.BytesIO(docx_bytes),
#         media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#         headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
#     )


@router.get("/download/{review_id}/clean")
def download_clean_copy(
    review_id: str,
    findings: str = "",
    session: Session = Depends(get_session)
):
    """
    Download 3: Full NDA with selected Red + Amber changes applied.

    Query param 'findings' is a comma-separated list of finding IDs to apply.
    If empty or not provided, applies all Red/Amber findings.
    """
    review, doc, all_findings = _get_review_doc_findings(review_id, session)

    # Filter findings based on selected IDs
    if findings:
        selected_ids = {str(fid).strip() for fid in findings.split(',') if str(fid).strip()}
        filtered_findings = [f for f in all_findings if str(f['id']) in selected_ids]
    else:
        # Default: apply all Red and Amber findings
        filtered_findings = [f for f in all_findings if f['rag_rating'] in ('Red', 'Amber')]

    try:
        docx_bytes = generate_clean_copy(
            doc.file_bytes, doc.filename, filtered_findings, raw_text=doc.raw_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clean copy: {e}")

    safe_name = doc.filename.rsplit(".", 1)[0] + "_clean_copy.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store",
        },
    )


# Legacy endpoint
@router.get("/download/{review_id}/docx")
def download_redline_legacy(review_id: str, session: Session = Depends(get_session)):
    return download_issues_report(review_id, session)
