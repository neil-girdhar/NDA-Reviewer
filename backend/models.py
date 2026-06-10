from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


class Document(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    filename: str
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    raw_text: str
    file_bytes: bytes

    reviews: List["Review"] = Relationship(back_populates="document")


class Review(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="document.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    overall_risk: str  # "Red" | "Amber" | "Green"
    model_used: str
    saved: bool = False

    document: Optional[Document] = Relationship(back_populates="reviews")
    findings: List["ClauseFinding"] = Relationship(back_populates="review")


class ClauseFinding(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    review_id: str = Field(foreign_key="review.id")
    clause_type: str
    original_text: str
    rag_rating: str  # "Red" | "Amber" | "Green"
    plain_english_summary: str
    risk_reason: str
    suggested_redline: str
    replacement_language: str
    talking_points: str = Field(default="")

    review: Optional[Review] = Relationship(back_populates="findings")


# --- Response schemas (not table models) ---

class ClauseFindingRead(SQLModel):
    id: str
    clause_type: str
    original_text: str
    rag_rating: str
    plain_english_summary: str
    risk_reason: str
    suggested_redline: str
    replacement_language: str
    talking_points: str = ""


class ReviewRead(SQLModel):
    id: str
    document_id: str
    created_at: datetime
    overall_risk: str
    model_used: str
    saved: bool
    filename: str
    findings: List[ClauseFindingRead]


class ReviewSummary(SQLModel):
    id: str
    document_id: str
    created_at: datetime
    overall_risk: str
    filename: str
    saved: bool
