"""Generate redline and clean-copy .docx outputs from NDA findings."""
import io
import logging
import re
import unicodedata
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

from docx import Document as DocxDocument
from docx.shared import RGBColor, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

_PURPLE = RGBColor(0x6B, 0x46, 0xC1)
_RED    = RGBColor(0xCC, 0x00, 0x00)
_GREEN  = RGBColor(0x00, 0x80, 0x00)
_AMBER  = RGBColor(0xCC, 0x66, 0x00)
_GREY   = RGBColor(0x60, 0x60, 0x60)
_RAG_COLORS = {"Red": _PURPLE, "Red": _RED, "Amber": _AMBER, "Green": _GREEN}
_RAG_ORDER  = {"Red": 0, "Red": 1, "Amber": 2, "Green": 3}   # lower = higher priority


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _add_run(para, text: str, bold=False, italic=False, strike=False, color=None):
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.strike = strike
    if color:
        run.font.color.rgb = color
    return run


def _finding_position(finding: dict, raw_text: str) -> int:
    """
    Return the character position where this finding's content first appears
    in the raw NDA text — used for contract-order sorting.
    """
    raw_lower = raw_text.lower()

    # 1. Try the suggested_redline (first 80 chars to avoid noise)
    redline = finding.get("suggested_redline", "").strip()
    if redline:
        snippet = redline[:80].lower()
        pos = raw_lower.find(snippet)
        if pos != -1:
            return pos

    # 2. Try the clause_type as a keyword
    clause = finding.get("clause_type", "").lower()
    pos = raw_lower.find(clause)
    if pos != -1:
        return pos

    return len(raw_text)   # push unknowns to the end


def _match_finding(para_text: str, findings: List[dict]) -> Optional[dict]:
    """
    Two-pass matcher: exact/substring first, word-overlap second.
    Only considers Red and Amber findings that have replacement language.
    """
    if not para_text.strip():
        return None

    candidates = [
        f for f in findings
        if f["rag_rating"] != "Green" and f.get("replacement_language")
    ]

    # Pass 1 — direct substring match (case-insensitive)
    para_lower = para_text.lower()
    for f in candidates:
        original = f.get("suggested_redline", "").strip()
        if original and original.lower() in para_lower:
            return f

    # Pass 2 — word overlap (threshold ≥ 4 words)
    best, best_score = None, 0
    para_words = set(para_lower.split())
    for f in candidates:
        original = f.get("suggested_redline", "").lower()
        if not original:
            continue
        orig_words = set(original.split())
        score = len(orig_words & para_words)
        if score > best_score and score >= 4:
            best_score = score
            best = f
    return best


def _replace_paragraph_text(para, new_text: str):
    """Replace all runs in a paragraph with new_text, preserving the first run's style."""
    for run in para.runs:
        run.text = ""
    if para.runs:
        para.runs[0].text = new_text
    else:
        para.add_run(new_text)


def _apply_substring_replacement(para, finding: dict) -> bool:
    """
    If suggested_redline is a substring of the paragraph, replace only that
    substring with replacement_language (surgical — preserves surrounding text).
    Returns True if a replacement was made.
    """
    original    = finding.get("suggested_redline", "").strip()
    replacement = finding.get("replacement_language", "").strip()
    if not original or not replacement:
        return False

    full_text = para.text
    # Case-insensitive match
    match = re.search(re.escape(original), full_text, flags=re.IGNORECASE)
    if not match:
        return False

    new_text = full_text[:match.start()] + replacement + full_text[match.end():]
    _replace_paragraph_text(para, new_text)
    return True


def _extract_raw_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
    else:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ─────────────────────────────────────────────
# Download 1 — Issues Report (contract order)
# ─────────────────────────────────────────────

def generate_issues_report(
    file_bytes: bytes,
    filename: str,
    findings: List[dict],
    raw_text: str = "",
) -> bytes:
    """
    Standalone DOCX showing only Red and Amber findings in the order
    they appear in the contract. Each finding shows the original text
    struck out in red and the replacement in green.
    """
    issues = [f for f in findings if f["rag_rating"] in ("Red", "Amber")]

    # Sort by severity (Red → Amber), then by position within each group
    issues.sort(key=lambda f: (
        _RAG_ORDER.get(f["rag_rating"], 9),
        _finding_position(f, raw_text) if raw_text else 0,
    ))

    doc = DocxDocument()

    # Cover heading
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(title, "NDA Issues Report", bold=True).font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(sub, f"Document: {filename}", italic=True)
    doc.add_paragraph()

    # Summary counts
    red_count   = sum(1 for f in findings if f["rag_rating"] == "Red")
    amber_count = sum(1 for f in findings if f["rag_rating"] == "Amber")
    green_count = sum(1 for f in findings if f["rag_rating"] == "Green")
    summary = doc.add_paragraph()
    summary.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(summary, f"  {red_count} Red  ",   bold=True, color=_RED)
    _add_run(summary, f"  {amber_count} Amber  ", bold=True, color=_AMBER)
    _add_run(summary, f"  {green_count} Green  ", bold=True, color=_GREEN)
    doc.add_paragraph()

    if not issues:
        doc.add_paragraph("No Red or Amber issues found — the NDA is acceptable as written.")
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    for f in issues:
        rating = f["rag_rating"]
        color  = _RAG_COLORS[rating]

        # Clause heading
        heading = doc.add_paragraph()
        _add_run(heading, f"● {rating.upper()}  ", bold=True, color=color)
        _add_run(heading, f["clause_type"], bold=True)

        # Plain-English summary
        s = doc.add_paragraph()
        _add_run(s, "What it says: ", bold=True)
        _add_run(s, f["plain_english_summary"])

        # Risk reason
        r = doc.add_paragraph()
        _add_run(r, "Why it matters: ", bold=True)
        _add_run(r, f["risk_reason"], italic=True, color=_GREY)

        # Redline
        if f.get("suggested_redline"):
            old_p = doc.add_paragraph()
            _add_run(old_p, "Remove:  ", bold=True, color=_RED)
            _add_run(old_p, f["suggested_redline"], strike=True, color=_RED)

        if f.get("replacement_language"):
            new_p = doc.add_paragraph()
            _add_run(new_p, "Replace with:  ", bold=True, color=_GREEN)
            _add_run(new_p, f["replacement_language"], color=_GREEN)

        doc.add_paragraph("─" * 80)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# Download 2 — Negotiation Pack (redlines + talking points)
# ─────────────────────────────────────────────

_INDIGO = RGBColor(0x31, 0x2E, 0x81)   # dark indigo for talking-point text
_INDIGO_HEAD = RGBColor(0x4F, 0x46, 0xE5)  # brighter indigo for the label


def generate_negotiation_pack(
    file_bytes: bytes,
    filename: str,
    findings: List[dict],
    raw_text: str = "",
) -> bytes:
    """
    Combines the Issues Report with per-finding talking points.
    Intended for the Ascential BD / project manager who will push back
    on the counterparty — they get the redlines AND the conversation script.
    """
    issues = [f for f in findings if f["rag_rating"] in ("Red", "Amber")]

    # Sort by severity (Red → Amber), then by position within each group
    issues.sort(key=lambda f: (
        _RAG_ORDER.get(f["rag_rating"], 9),
        _finding_position(f, raw_text) if raw_text else 0,
    ))

    doc = DocxDocument()

    # ── Cover ─────────────────────────────────────────────────────────────────
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(title, "NDA Negotiation Pack", bold=True).font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(sub, f"Document: {filename}", italic=True)

    sub2 = doc.add_paragraph()
    sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(
        sub2,
        "Redlines + talking points for Ascential BD / project manager use",
        italic=True,
        color=_GREY,
    ).font.size = Pt(9)
    doc.add_paragraph()

    # ── Summary counts ────────────────────────────────────────────────────────
    red_count   = sum(1 for f in findings if f["rag_rating"] == "Red")
    amber_count = sum(1 for f in findings if f["rag_rating"] == "Amber")
    green_count = sum(1 for f in findings if f["rag_rating"] == "Green")
    summary = doc.add_paragraph()
    summary.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(summary, f"  {red_count} Red  ",     bold=True, color=_RED)
    _add_run(summary, f"  {amber_count} Amber  ", bold=True, color=_AMBER)
    _add_run(summary, f"  {green_count} Green  ", bold=True, color=_GREEN)
    doc.add_paragraph()

    if not issues:
        doc.add_paragraph("No Red or Amber issues found — the NDA is acceptable as written.")
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    for f in issues:
        rating = f["rag_rating"]
        color  = _RAG_COLORS[rating]

        # Clause heading
        heading = doc.add_paragraph()
        _add_run(heading, f"● {rating.upper()}  ", bold=True, color=color)
        _add_run(heading, f["clause_type"], bold=True)

        # Plain-English summary
        s = doc.add_paragraph()
        _add_run(s, "What it says: ", bold=True)
        _add_run(s, f["plain_english_summary"])

        # Risk reason
        r = doc.add_paragraph()
        _add_run(r, "Why it matters: ", bold=True)
        _add_run(r, f["risk_reason"], italic=True, color=_GREY)

        # Redline
        if f.get("suggested_redline"):
            old_p = doc.add_paragraph()
            _add_run(old_p, "Remove:  ", bold=True, color=_RED)
            _add_run(old_p, f["suggested_redline"], strike=True, color=_RED)

        if f.get("replacement_language"):
            new_p = doc.add_paragraph()
            _add_run(new_p, "Replace with:  ", bold=True, color=_GREEN)
            _add_run(new_p, f["replacement_language"], color=_GREEN)

        # Talking points (only if present)
        tp = (f.get("talking_points") or "").strip()
        if tp:
            tp_label = doc.add_paragraph()
            tp_label.paragraph_format.space_before = Pt(4)
            _add_run(tp_label, "💬 Talking points:", bold=True, color=_INDIGO_HEAD)

            for line in tp.splitlines():
                line = line.strip()
                if not line:
                    continue
                tp_p = doc.add_paragraph(style="List Bullet")
                tp_p.paragraph_format.left_indent = Pt(18)
                _add_run(tp_p, line, color=_INDIGO)

        doc.add_paragraph("─" * 80)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# Download 3 — Clean Final Copy
# ─────────────────────────────────────────────

def generate_clean_copy(
    file_bytes: bytes,
    filename: str,
    findings: List[dict],
    raw_text: str = "",
) -> bytes:
    """
    Full NDA with every Red/Amber change applied — word-for-word.

    For DOCX files: operates directly on the original DOCX paragraph objects,
    bypassing text extraction entirely.  This preserves all original formatting,
    styles, and structure, and eliminates the text-normalisation mismatches that
    caused substitutions to fail in the legacy 6-pass approach.

    For PDF files: falls back to the clause-based text substitution path.

    Green clauses are always left completely untouched.
    """
    if filename.lower().endswith(".docx"):
        return _generate_clean_copy_docx(file_bytes, filename, findings)

    # ── PDF path (unchanged) ──────────────────────────────────────────────────
    from services.parser import segment_clauses   # local import to avoid circular

    if not raw_text:
        raw_text = _extract_raw_text(file_bytes, filename)

    clauses = segment_clauses(raw_text)

    if clauses:
        modified_clauses, failed_subs = _apply_clause_substitutions(clauses, findings, raw_text=raw_text)
        if failed_subs:
            log.warning(
                "generate_clean_copy: %d substitution(s) failed all 6 passes and were "
                "NOT applied. A warning section has been appended to the output document.",
                len(failed_subs),
            )
        return _build_docx_from_clauses(modified_clauses, filename, failed_subs=failed_subs)
    else:
        modified_text = _apply_all_substitutions(raw_text, findings)
        return _build_docx_from_text(modified_text, filename)


def _generate_clean_copy_docx(
    file_bytes: bytes,
    filename: str,
    findings: List[dict],
) -> bytes:
    """
    Generate a clean copy by directly modifying the original DOCX paragraph objects.

    Works in three passes per finding:
    1. Exact substring match (case-insensitive) — surgical replacement
    2. Normalised text match (handles smart quotes, em-dashes, Unicode variants)
    3. Whitespace-flexible regex — handles line-break differences

    Absent clauses (no suggested_redline) are appended as new sections.
    Unmatched findings are collected and listed in an appendix table so
    reviewers can see every required change, even those that could not be
    placed automatically.
    """
    doc = DocxDocument(io.BytesIO(file_bytes))

    applicable = [
        f for f in findings
        if f.get("rag_rating") != "Green" and f.get("replacement_language", "").strip()
    ]
    failed: List[dict] = []

    for f in applicable:
        original    = f.get("suggested_redline",    "").strip()
        replacement = f.get("replacement_language", "").strip()

        if not original:
            # Absent clause — append as a new titled section at the end
            h = doc.add_paragraph()
            _add_run(h, f.get("clause_type", "Additional Provision"), bold=True)
            b = doc.add_paragraph()
            b.add_run(replacement)
            log.debug("finding '%s': absent clause → appended new section", f.get("clause_type"))
            continue

        norm_original = _normalize_text(original)
        repl = lambda m, r=replacement: r   # avoids regex back-ref expansion
        matched = False

        # Pass 1 — exact case-insensitive substring in original paragraph text
        for para in doc.paragraphs:
            if _apply_substring_replacement(para, f):
                matched = True
                log.debug("finding '%s': Pass 1 (exact) in paragraph", f.get("clause_type"))
                break

        if not matched:
            # Pass 2 — normalised text match (Unicode cleanup)
            for para in doc.paragraphs:
                norm_para = _normalize_text(para.text)
                if norm_original in norm_para:
                    new_text = norm_para.replace(norm_original, replacement, 1)
                    _replace_paragraph_text(para, new_text)
                    matched = True
                    log.debug("finding '%s': Pass 2 (normalised) in paragraph",
                              f.get("clause_type"))
                    break

        if not matched:
            # Pass 3 — whitespace-flexible regex on normalised paragraph text
            ws_pat = _ws_pattern(norm_original)
            if ws_pat:
                for para in doc.paragraphs:
                    norm_para = _normalize_text(para.text)
                    result = re.sub(ws_pat, repl, norm_para, count=1, flags=re.IGNORECASE)
                    if result != norm_para:
                        _replace_paragraph_text(para, result)
                        matched = True
                        log.debug("finding '%s': Pass 3 (ws-flex) in paragraph",
                                  f.get("clause_type"))
                        break

        if not matched:
            log.warning(
                "finding '%s' (rag=%s): NOT matched in DOCX paragraphs — "
                "appending as REQUIRED CHANGE. suggested_redline[:80]=%r",
                f.get("clause_type"), f.get("rag_rating"), original[:80],
            )
            failed.append(f)

    # Append failed substitutions as clearly labeled sections + summary table
    if failed:
        doc.add_paragraph()
        warn_h = doc.add_paragraph()
        _add_run(warn_h, "REQUIRED CHANGES — MANUAL REVIEW NEEDED", bold=True, color=_RED)
        warn_h.runs[0].font.size = Pt(13)

        note = doc.add_paragraph()
        _add_run(
            note,
            "The following change(s) could not be placed automatically. "
            "Locate each clause in the document and apply the replacement language below "
            "before sending this copy to the counterparty.",
            color=_RED,
        )

        for f in failed:
            entry_h = doc.add_paragraph()
            _add_run(entry_h, f"REQUIRED CHANGE — {f.get('clause_type', 'Unknown')}: ",
                     bold=True, color=_RED)
            entry_b = doc.add_paragraph()
            entry_b.add_run(f.get("replacement_language", ""))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _normalize_text(text: str) -> str:
    """Normalize text for reliable string matching.

    Converts the most common Unicode variants that differ between pdfplumber
    PDF extraction and Claude JSON output:
    - NFKC normalization (ligatures fi/fl -> fi/fl, composed chars)
    - Smart/curly quotes  ->  ASCII straight quotes (by code point)
    - Em/en/figure dashes ->  hyphen
    - Non-breaking/thin/figure spaces -> regular space
    - Zero-width chars (joiners, BOM, etc.) -> removed
    - Soft hyphen U+00AD (PDF line-break artefact) -> removed
    - Multiple spaces -> single space
    """
    text = unicodedata.normalize('NFKC', text)
    # Smart quotes -> ASCII straight (by code point, no literal Unicode)
    text = (text
            .replace(chr(0x2018), chr(0x27))  # left single quotation mark
            .replace(chr(0x2019), chr(0x27))  # right single quotation mark
            .replace(chr(0x201C), chr(0x22))  # left double quotation mark
            .replace(chr(0x201D), chr(0x22))  # right double quotation mark
            .replace(chr(0x2032), chr(0x27))  # prime
            .replace(chr(0x2033), chr(0x22))  # double prime
            )
    # Dashes -> hyphen
    text = (text
            .replace(chr(0x2014), '--')  # em dash
            .replace(chr(0x2013), '-')   # en dash
            .replace(chr(0x2012), '-')   # figure dash
            .replace(chr(0x2011), '-')   # non-breaking hyphen
            )
    # Special spaces -> regular space
    for _cp in (0x00A0, 0x202F, 0x2009, 0x2007, 0x2008, 0x205F):
        text = text.replace(chr(_cp), ' ')
    # Zero-width / invisible chars -> remove
    for _cp in (0x2060, 0xFEFF, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x00AD):
        text = text.replace(chr(_cp), '')
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text

def _ws_pattern(text: str) -> str:
    """
    Build a regex pattern from text where any run of whitespace (spaces,
    newlines, tabs) between words is treated as \\s+.  This handles the most
    common mismatch between Claude's extracted redline text and the source
    document's actual line-breaks and indentation.
    """
    return r'\s+'.join(re.escape(tok) for tok in text.split())


def _apply_clause_substitutions(
    clauses: List[dict],
    findings: List[dict],
    raw_text: str = "",
) -> Tuple[List[dict], List[dict]]:
    """
    Apply Red/Amber substitutions within individual clause bodies.

    Matching strategy (6 passes, most precise → most permissive):

    Passes 1–4 operate on space-joined clause bodies (same format Claude saw).
    Pass 5 falls back to clause-type keyword matching (replaces full body).
    Pass 6 searches in raw_text (original PDF newlines) — catches cases where
        Claude extracted suggested_redline from raw_text rather than the
        space-joined clauses_text.

    All text comparisons use _normalize_text() to neutralise unicode differences
    (smart quotes, em-dashes, ligatures, non-breaking spaces, soft hyphens)
    that are common between pdfplumber output and Claude's JSON response.

    All replacements are VERBATIM: replacement_language is copied exactly as
    stored in the database, preserving any user edits made in the UI.
    """
    # Deep copy — never mutate the input
    modified = [{"heading": c["heading"], "body": c["body"]} for c in clauses]
    appended: List[dict] = []
    failed:   List[dict] = []

    # Pre-normalise clause bodies for matching (keep originals in modified for output)
    norm_bodies = [_normalize_text(c["body"]) for c in modified]

    applicable = [
        f for f in findings
        if f["rag_rating"] != "Green" and f.get("replacement_language", "").strip()
    ]

    for f in applicable:
        original    = f.get("suggested_redline",    "").strip()
        replacement = f.get("replacement_language", "").strip()

        if not original:
            # Absent clause — append as a new section
            appended.append({
                "heading": f.get("clause_type", "Additional Provision"),
                "body":    replacement,
            })
            log.debug("finding '%s': no suggested_redline → appended as new section",
                      f.get("clause_type"))
            continue

        norm_original = _normalize_text(original)
        repl = lambda m, r=replacement: r   # avoids regex back-ref expansion

        matched = False

        # ── Pass 1: exact match on normalised bodies ──────────────────────────
        # We work entirely on the normalised body to avoid index mismatches
        # (normalisation can change string length, so raw-body slicing is unsafe).
        for i, clause in enumerate(modified):
            if norm_original in norm_bodies[i]:
                start = norm_bodies[i].find(norm_original)
                end   = start + len(norm_original)
                modified[i]["body"] = (
                    norm_bodies[i][:start] + replacement + norm_bodies[i][end:]
                )
                norm_bodies[i] = _normalize_text(modified[i]["body"])
                matched = True
                log.debug("finding '%s': matched Pass 1 in clause '%s'",
                          f.get("clause_type"), clause["heading"])
                break

        if matched:
            continue

        # ── Pass 2: case-insensitive regex on normalised bodies ───────────────
        for i, clause in enumerate(modified):
            result = re.sub(re.escape(norm_original), repl, norm_bodies[i],
                            count=1, flags=re.IGNORECASE)
            if result != norm_bodies[i]:
                modified[i]["body"] = result
                norm_bodies[i] = result
                matched = True
                log.debug("finding '%s': matched Pass 2 in clause '%s'",
                          f.get("clause_type"), clause["heading"])
                break

        if matched:
            continue

        # ── Pass 3: whitespace-flexible match on normalised bodies ────────────
        ws_pat = _ws_pattern(norm_original)
        if ws_pat:
            for i, clause in enumerate(modified):
                result = re.sub(ws_pat, repl, norm_bodies[i],
                                count=1, flags=re.IGNORECASE)
                if result != norm_bodies[i]:
                    modified[i]["body"] = result
                    norm_bodies[i] = result
                    matched = True
                    log.debug("finding '%s': matched Pass 3 (ws-flex) in clause '%s'",
                              f.get("clause_type"), clause["heading"])
                    break

        if matched:
            continue

        # ── Pass 4: first-sentence anchor (≥20 chars) ─────────────────────────
        first_sentence = re.split(r'(?<=[.!?])\s', norm_original)[0].strip()
        if len(first_sentence) >= 20:
            ws_pat_fs = _ws_pattern(first_sentence)
            for i, clause in enumerate(modified):
                result = re.sub(ws_pat_fs, repl, norm_bodies[i],
                                count=1, flags=re.IGNORECASE)
                if result != norm_bodies[i]:
                    modified[i]["body"] = result
                    norm_bodies[i] = result
                    matched = True
                    log.debug("finding '%s': matched Pass 4 (first-sentence) in clause '%s'",
                              f.get("clause_type"), clause["heading"])
                    break

        if matched:
            continue

        # ── Pass 5: clause_type heading keyword → replace entire body ─────────
        clause_type = f.get("clause_type", "")
        if clause_type:
            keywords = [w for w in re.split(r'\W+', clause_type) if len(w) >= 4]
            if keywords:
                for i, clause in enumerate(modified):
                    heading_lower = clause["heading"].lower()
                    if all(kw.lower() in heading_lower for kw in keywords[:2]):
                        modified[i]["body"] = replacement
                        norm_bodies[i] = _normalize_text(replacement)
                        matched = True
                        log.debug("finding '%s': matched Pass 5 (heading) '%s'",
                                  f.get("clause_type"), clause["heading"])
                        break

        if matched:
            continue

        # ── Pass 6: search raw_text, map back to closest clause ───────────────
        # Claude sometimes quotes from the full raw_text (which has original
        # PDF newlines) rather than the space-joined clause bodies.  Here we
        # find the match in raw_text, then identify which clause body best
        # overlaps with the surrounding context, and apply the replacement there.
        if raw_text:
            norm_raw = _normalize_text(raw_text)
            ws_pat_raw = _ws_pattern(norm_original)
            m = re.search(ws_pat_raw, norm_raw, flags=re.IGNORECASE) if ws_pat_raw else None
            if m:
                match_pos = m.start()
                # 300-char context window around the match to identify the clause
                ctx_start = max(0, match_pos - 300)
                ctx_end   = min(len(norm_raw), m.end() + 300)
                context   = norm_raw[ctx_start:ctx_end]
                ctx_words = set(context.lower().split())

                best_idx, best_score = 0, 0
                for i, nb in enumerate(norm_bodies):
                    body_words = set(nb.lower().split())
                    score = len(body_words & ctx_words)
                    if score > best_score:
                        best_score = score
                        best_idx = i

                if best_score >= 3:
                    # Try surgical replacement within the identified clause body
                    body = norm_bodies[best_idx]
                    result = re.sub(ws_pat_raw, repl, body, count=1, flags=re.IGNORECASE)
                    if result != body:
                        modified[best_idx]["body"] = result
                        norm_bodies[best_idx] = result
                    else:
                        # Fall back: insert replacement as a sentence appended to the body
                        # rather than silently dropping it
                        modified[best_idx]["body"] = (
                            modified[best_idx]["body"].rstrip(". ") + ".  " + replacement
                        )
                        norm_bodies[best_idx] = _normalize_text(modified[best_idx]["body"])
                    matched = True
                    log.debug("finding '%s': matched Pass 6 (raw_text) via clause '%s'",
                              f.get("clause_type"), modified[best_idx]["heading"])

        if not matched:
            log.warning(
                "finding '%s' (rag=%s): suggested_redline NOT matched in any pass — "
                "appending replacement at end of document. suggested_redline[:120]=%r",
                f.get("clause_type"), f.get("rag_rating"),
                original[:120],
            )
            # Could not locate the exact text to replace — append the replacement
            # as a new labeled section so it is still present in the clean copy.
            # The reviewer must move it to the correct clause location manually.
            appended.append({
                "heading": f"REQUIRED CHANGE — {f.get('clause_type', 'Unknown')}",
                "body": replacement,
            })
            failed.append({
                "clause_type":          f.get("clause_type", "Unknown"),
                "rag_rating":           f.get("rag_rating", ""),
                "suggested_redline":    original,
                "replacement_language": replacement,
            })

    return modified + appended, failed


def _apply_all_substitutions(raw_text: str, findings: List[dict]) -> str:
    """
    Fallback: apply substitutions directly to raw full-document text.
    Used only when segment_clauses() returns nothing (unstructured plain text).
    """
    modified = raw_text

    for f in findings:
        if f["rag_rating"] == "Green":
            continue
        original    = f.get("suggested_redline",    "").strip()
        replacement = f.get("replacement_language", "").strip()
        if not replacement:
            continue

        repl = lambda m, r=replacement: r

        if original:
            if original in modified:
                modified = modified.replace(original, replacement, 1)
                continue
            ws_pat = _ws_pattern(original)
            if ws_pat:
                result = re.sub(ws_pat, repl, modified, count=1, flags=re.IGNORECASE)
                if result != modified:
                    modified = result
                    continue
            result = re.sub(re.escape(original), repl, modified,
                            count=1, flags=re.IGNORECASE)
            if result != modified:
                modified = result
                continue

        clause_type = f.get("clause_type", "")
        if clause_type:
            keywords = [w for w in re.split(r'\W+', clause_type) if len(w) >= 4]
            if keywords:
                heading_pattern = r'(?im)^[^\n]*' + r'[^\n]*'.join(
                    re.escape(kw) for kw in keywords[:2]
                ) + r'[^\n]*$'
                heading_match = re.search(heading_pattern, modified)
                if heading_match:
                    after_heading = modified[heading_match.end():]
                    body_match    = re.match(r'\s*\n+(.*?)(\n\n|\Z)', after_heading, re.DOTALL)
                    if body_match:
                        old_body = body_match.group(0)
                        new_body = "\n\n" + replacement + "\n\n"
                        modified = (
                            modified[:heading_match.end()]
                            + modified[heading_match.end():].replace(old_body, new_body, 1)
                        )

    return modified


def _docx_header_body(doc, clauses: List[dict]) -> None:
    """Render a list of {heading, body} clause dicts into an open Document."""
    for clause in clauses:
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after  = Pt(3)
        r = _add_run(h, clause["heading"], bold=True)
        r.font.size = Pt(11)

        if clause["body"].strip():
            b = doc.add_paragraph()
            b.paragraph_format.space_before = Pt(0)
            b.paragraph_format.space_after  = Pt(10)
            r = b.add_run(clause["body"].strip())
            r.font.size = Pt(10.5)


def _docx_cover(doc, subtitle: str) -> None:
    """Add the standard NDA title + subtitle to an open Document."""
    for section in doc.sections:
        section.top_margin    = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin   = Inches(1.25)
        section.right_margin  = Inches(1.25)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after  = Pt(6)
    r = _add_run(title, "NON-DISCLOSURE AGREEMENT", bold=True)
    r.font.size = Pt(14)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_before = Pt(0)
    sub.paragraph_format.space_after  = Pt(28)
    r = _add_run(sub, subtitle, italic=True, color=_GREY)
    r.font.size = Pt(9)


def _build_docx_from_clauses(
    clauses: List[dict],
    filename: str,
    failed_subs: Optional[List[dict]] = None,
) -> bytes:
    """
    Build a clean DOCX directly from a list of {heading, body} clause dicts.
    Preferred over _build_docx_from_text because it avoids a second round-trip
    through segment_clauses() which could mis-parse modified text.

    If failed_subs is non-empty, a final page is appended listing every
    substitution that could not be automatically applied, so the reviewer
    can locate and fix them manually before sending the document.
    """
    doc = DocxDocument()
    _docx_cover(doc, "Clean Copy — all Ascential-required changes applied by NDA Reviewer")
    _docx_header_body(doc, clauses)

    if failed_subs:
        doc.add_page_break()

        h = doc.add_paragraph()
        _add_run(h, "UNRESOLVED CHANGES — MANUAL REVIEW REQUIRED", bold=True, color=_RED)
        h.runs[0].font.size = Pt(13)

        sub = doc.add_paragraph()
        _add_run(
            sub,
            "The following clause(s) could not be automatically placed in context. "
            "Each has been appended at the end of the main document body under a "
            "‘REQUIRED CHANGE’ heading — move each to the correct clause location "
            "before sending this document to the counterparty.",
            color=_RED,
        )
        sub.runs[0].font.size = Pt(10)

        tbl = doc.add_table(rows=1 + len(failed_subs), cols=4)
        tbl.style = "Table Grid"
        for col, header in enumerate(
            ["Rating", "Clause Type", "Original Text (to remove)", "Replacement Language"]
        ):
            cell = tbl.cell(0, col)
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True

        for i, fs in enumerate(failed_subs, start=1):
            tbl.cell(i, 0).text = fs["rag_rating"]
            tbl.cell(i, 1).text = fs["clause_type"]
            tbl.cell(i, 2).text = fs["suggested_redline"][:500]
            tbl.cell(i, 3).text = fs["replacement_language"][:500]
            color = _RAG_COLORS.get(fs["rag_rating"])
            if color and tbl.cell(i, 0).paragraphs[0].runs:
                tbl.cell(i, 0).paragraphs[0].runs[0].font.color.rgb = color

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_docx_from_text(modified_text: str, filename: str) -> bytes:
    """
    Rebuild a clean DOCX from plain text.  Used only as a fallback when
    segment_clauses() found no clause structure in the document.
    - 1.25" left/right margins, 1" top/bottom
    - 14 pt bold centred title, 11 pt bold section headings, 10.5 pt body
    """
    from services.parser import segment_clauses   # local import to avoid circular

    doc = DocxDocument()
    _docx_cover(doc, "Clean Copy — all Ascential-required changes applied by NDA Reviewer")

    clauses = segment_clauses(modified_text)
    if not clauses:
        # No structure — split on double newlines
        for para_text in modified_text.split("\n\n"):
            para_text = para_text.strip()
            if para_text:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(8)
                p.add_run(para_text).font.size = Pt(10.5)
    else:
        _docx_header_body(doc, clauses)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()



# ─────────────────────────────────────────────
# Legacy alias
# ─────────────────────────────────────────────

def generate_redline(file_bytes: bytes, filename: str, findings: List[dict]) -> bytes:
    return generate_issues_report(file_bytes, filename, findings)
