"""Extract text from PDF/DOCX and segment into clauses."""
import io
import json
import re
import unicodedata
from typing import List

from docx import Document as DocxDocument


def sanitize_text(text: str) -> str:
    """Remove PDF/DOCX Unicode artifacts before segmentation or analysis."""
    text = unicodedata.normalize('NFKC', text)
    # Soft hyphens and zero-width characters (PDF line-break artefacts)
    for cp in (0x00AD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF):
        text = text.replace(chr(cp), '')
    # Non-breaking and typographic spaces → regular space
    for cp in (0x00A0, 0x202F, 0x2009, 0x2007, 0x2008, 0x205F):
        text = text.replace(chr(cp), ' ')
    return text


def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return sanitize_text(_extract_pdf(file_bytes))
    elif ext == "docx":
        return sanitize_text(_extract_docx(file_bytes))
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except Exception:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()


def _extract_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


# Patterns that typically start a new clause heading
_HEADING_RE = re.compile(
    r"^(?:"
    r"\d+\.\s"             # 1. or 2.
    r"|\d+\.\d+\s"         # 1.1 or 2.3
    r"|[A-Z]{2,}[^a-z]*$"  # ALL CAPS heading line
    r"|Article\s+\w"       # Article I / Article 1
    r"|Section\s+\d"       # Section 1
    r")",
    re.IGNORECASE,
)


def _is_heading_para(para) -> bool:
    """
    Detect clause headings using DOCX paragraph structure — far more reliable
    than regex on plain text because it sees style names and bold formatting.
    """
    text = para.text.strip()
    if not text or len(text) > 120:
        return False

    # Style-based detection: any paragraph style that starts with "Heading"
    try:
        if para.style and para.style.name and para.style.name.lower().startswith("heading"):
            return True
    except Exception:
        pass

    # Bold-run detection: every non-empty run is bold
    runs = [r for r in para.runs if r.text.strip()]
    if runs and all(r.bold for r in runs):
        return True

    # Regex patterns as a final fallback (preserve existing detection behaviour)
    if _HEADING_RE.match(text):
        return True

    return False


def segment_clauses(text: str) -> List[dict]:
    """
    Return list of {heading, body} dicts — text-based regex segmentation.
    Used for PDFs and as a fallback when DOCX paragraph structure is unavailable.
    """
    text = sanitize_text(text)
    lines = text.splitlines()
    clauses: List[dict] = []
    current_heading = "Preamble"
    current_body: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADING_RE.match(stripped) and len(stripped) < 120:
            if current_body:
                clauses.append({
                    "heading": current_heading,
                    "body": " ".join(current_body).strip(),
                })
            current_heading = stripped
            current_body = []
        else:
            current_body.append(stripped)

    if current_body:
        clauses.append({
            "heading": current_heading,
            "body": " ".join(current_body).strip(),
        })

    return clauses


def segment_clauses_docx(file_bytes: bytes) -> List[dict]:
    """
    Segment a DOCX file into clauses using paragraph style and formatting data.

    Detection priority:
    1. DOCX paragraph styles (Heading 1 / Heading 2 / etc.) — most reliable
    2. Bold-run detection — catches NDAs styled without Heading styles
    3. Regex patterns — existing fallback for numbered sections / ALL CAPS

    If structural detection produces fewer than 5 clauses, falls back to
    regex-based text segmentation then to a Claude Sonnet semantic pass.
    """
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = doc.paragraphs

    clauses: List[dict] = []
    current_heading = "Preamble"
    current_body: List[str] = []

    for para in paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if _is_heading_para(para):
            if current_body:
                clauses.append({
                    "heading": current_heading,
                    "body": " ".join(current_body),
                })
            current_heading = text
            current_body = []
        else:
            current_body.append(text)

    if current_body:
        clauses.append({
            "heading": current_heading,
            "body": " ".join(current_body),
        })

    # Fallback 1: regex-based text segmentation (if structural detection missed most clauses)
    if len(clauses) < 5:
        raw_text = "\n\n".join(p.text for p in paragraphs if p.text.strip())
        regex_clauses = segment_clauses(raw_text)
        if len(regex_clauses) > len(clauses):
            clauses = regex_clauses

    # Fallback 2: Claude Sonnet semantic segmentation (last resort)
    if len(clauses) < 5:
        raw_text = "\n\n".join(p.text for p in paragraphs if p.text.strip())
        semantic = _semantic_segment(raw_text)
        if len(semantic) > len(clauses):
            clauses = semantic

    return clauses


def _semantic_segment(raw_text: str) -> List[dict]:
    """
    Ask Claude Sonnet to identify clause headings when all heuristics fail.
    Returns empty list on any error so the caller can use its existing result.
    """
    try:
        import anthropic
        from config import settings
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": (
                    "The following is an NDA document. Identify all distinct clause sections "
                    "and return a JSON array. Each element must have exactly two keys: "
                    "\"heading\" (the section title or number as it appears in the document) "
                    "and \"body\" (the full text of that clause). "
                    "Return ONLY valid JSON — no markdown fences, no prose.\n\n"
                    f"{raw_text[:12000]}"
                ),
            }],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```[^\n]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except Exception:
        pass
    return []
