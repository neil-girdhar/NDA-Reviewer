"""Persist and retrieve reviews from SQLite."""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlmodel import Session, select

from models import Document, Review, ClauseFinding, ReviewRead, ReviewSummary, ClauseFindingRead


def save_review(session: Session, review: Review) -> None:
    review.saved = True
    session.add(review)
    session.commit()


def get_review(session: Session, review_id: str) -> Optional[ReviewRead]:
    review = session.get(Review, review_id)
    if not review:
        return None
    doc = session.get(Document, review.document_id)
    findings = session.exec(
        select(ClauseFinding).where(ClauseFinding.review_id == review_id)
    ).all()
    return ReviewRead(
        **review.model_dump(),
        filename=doc.filename if doc else "",
        findings=[ClauseFindingRead(**f.model_dump()) for f in findings],
    )


def purge_stale_reviews(session: Session, days: int = 30) -> int:
    """Delete unsaved reviews (and their orphaned documents) older than `days` days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    stale = session.exec(
        select(Review).where(Review.saved == False, Review.created_at < cutoff)
    ).all()
    if not stale:
        return 0

    stale_ids = [r.id for r in stale]
    doc_ids = list({r.document_id for r in stale})

    for review_id in stale_ids:
        for finding in session.exec(
            select(ClauseFinding).where(ClauseFinding.review_id == review_id)
        ).all():
            session.delete(finding)
    for r in stale:
        session.delete(r)
    session.commit()

    for doc_id in doc_ids:
        has_remaining = session.exec(
            select(Review).where(Review.document_id == doc_id)
        ).first()
        if not has_remaining:
            doc = session.get(Document, doc_id)
            if doc:
                session.delete(doc)
    session.commit()

    return len(stale_ids)


def list_saved_reviews(session: Session) -> List[ReviewSummary]:
    reviews = session.exec(select(Review).where(Review.saved == True)).all()
    results = []
    for r in reviews:
        doc = session.get(Document, r.document_id)
        results.append(ReviewSummary(
            id=r.id,
            document_id=r.document_id,
            created_at=r.created_at,
            overall_risk=r.overall_risk,
            filename=doc.filename if doc else "",
            saved=r.saved,
        ))
    return results
