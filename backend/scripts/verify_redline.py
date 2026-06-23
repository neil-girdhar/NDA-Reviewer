"""
Read-only verification harness for the redline engine (generate_issues_report).

Runs four checks:
  (a) Every Red/Amber finding NOT in the appendix has its replacement_language
      present in the body (tolerance ladder).
  (b) When >=1 finding applied inline, >=1 run is red+strike and >=1 run is green.
  (c) Two-findings-in-one-paragraph: both edits keep their colour (Bug #1 guard).
  (d) Cross-paragraph edit preserves trailing text in the next paragraph (Bug #2 guard).

Writes nothing: opens nda_reviews.db read-only, builds DOCX bytes in memory only.
Exit code is non-zero if any (a)/(b)/(c)/(d) assertion fails.
"""
import io
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docx import Document as DocxDocument
from docx.shared import RGBColor

from services.redline_service import (
    generate_issues_report,
    _iter_text_runs,
    _normalize_text,
    _ws_pattern,
    _RED,
    _GREEN,
)

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nda_reviews.db")
APPENDIX_MARKER = "Additional Required Changes"


def _present(text: str, full: str, norm_full: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t in full:
        return True
    nt = _normalize_text(t)
    if nt in norm_full:
        return True
    pat = _ws_pattern(nt)
    return bool(pat and re.search(pat, norm_full, re.IGNORECASE))


def _run_color(run):
    try:
        if run.font.color is not None and run.font.color.rgb is not None:
            return str(run.font.color.rgb)
    except Exception:
        pass
    return None


def _split_body_appendix(doc):
    """Return (body_text, applied_inline_present_flag) — body excludes appendix."""
    body_paras, in_appendix = [], False
    red_strike = green = 0
    for p in doc.paragraphs:
        txt = "".join(r.text for r in _iter_text_runs(p))
        if APPENDIX_MARKER in txt:
            in_appendix = True
        if not in_appendix:
            body_paras.append(txt)
            for r in _iter_text_runs(p):
                col = _run_color(r)
                if col == str(_RED) and r.font.strike:
                    red_strike += 1
                elif col == str(_GREEN):
                    green += 1
    return "\n".join(body_paras), red_strike, green


def check_db():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    reviews = cur.execute("SELECT id, document_id FROM review").fetchall()

    total = inline_any = fail_a = fail_b = 0
    appendix_routed = []

    for rev in reviews:
        doc_row = cur.execute("SELECT * FROM document WHERE id=?", (rev["document_id"],)).fetchone()
        if not doc_row or not str(doc_row["filename"]).lower().endswith(".docx"):
            continue
        findings = [dict(r) for r in cur.execute(
            "SELECT * FROM clausefinding WHERE review_id=?", (rev["id"],)).fetchall()]
        ra = [f for f in findings if f["rag_rating"] in ("Red", "Amber") and f.get("suggested_redline")]
        if not ra:
            continue
        total += 1
        try:
            data = generate_issues_report(doc_row["file_bytes"], doc_row["filename"], ra,
                                          raw_text=doc_row["raw_text"])
        except Exception as e:
            print(f"  [ERROR] review {rev['id']}: generation raised {e!r}")
            fail_a += 1
            continue

        gen = DocxDocument(io.BytesIO(data))
        full_all = "\n".join("".join(r.text for r in _iter_text_runs(p)) for p in gen.paragraphs)
        norm_all = _normalize_text(full_all)
        body, red_strike, green = _split_body_appendix(gen)

        # (a) every finding present somewhere (inline body OR appendix); track routing
        for f in ra:
            repl = (f.get("replacement_language") or "").strip()
            if not repl:
                continue
            if not _present(repl, full_all, norm_all):
                print(f"  [FAIL-a] review {rev['id']} clause {f['clause_type']!r}: "
                      f"replacement text NOT found anywhere in output")
                fail_a += 1
            elif not _present(repl, body, _normalize_text(body)):
                appendix_routed.append((rev["id"], f["clause_type"]))

        # (b) if anything applied inline, there must be red-strike AND green runs
        body_has_inline = any(
            _present((f.get("replacement_language") or ""), body, _normalize_text(body))
            for f in ra if (f.get("replacement_language") or "").strip()
        )
        if body_has_inline:
            inline_any += 1
            if red_strike < 1 or green < 1:
                print(f"  [FAIL-b] review {rev['id']}: inline edit present but "
                      f"red_strike={red_strike} green={green}")
                fail_b += 1

    con.close()
    print(f"\nDB sweep: {total} DOCX reviews with Red/Amber findings, "
          f"{inline_any} had inline edits.")
    print(f"  (a) replacement-present failures: {fail_a}")
    print(f"  (b) colour failures:              {fail_b}")
    if appendix_routed:
        print(f"  appendix-routed findings ({len(appendix_routed)}) — eyeball these:")
        for rid, ct in appendix_routed[:30]:
            print(f"      {rid[:8]}  {ct}")
    return fail_a, fail_b


def _mk_doc(paragraphs):
    d = DocxDocument()
    for t in paragraphs:
        d.add_paragraph(t)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def check_two_in_one_paragraph():
    """(c) Two findings whose originals sit in the SAME paragraph — both keep colour."""
    para = ("The Receiving Party shall hold all Information in strict confidence "
            "and shall return all materials upon request without exception.")
    file_bytes = _mk_doc(["Preamble paragraph.", para, "Closing paragraph."])
    findings = [
        {"id": "1", "rag_rating": "Amber", "clause_type": "Confidentiality",
         "suggested_redline": "hold all Information in strict confidence",
         "replacement_language": "hold all Information in strict confidence for three (3) years",
         "plain_english_summary": "", "risk_reason": ""},
        {"id": "2", "rag_rating": "Amber", "clause_type": "Return of Information",
         "suggested_redline": "return all materials upon request without exception",
         "replacement_language": "return all materials upon request, except for routine backups",
         "plain_english_summary": "", "risk_reason": ""},
    ]
    gen = DocxDocument(io.BytesIO(generate_issues_report(file_bytes, "t.docx", findings)))
    red_strike = green = 0
    for p in gen.paragraphs:
        for r in _iter_text_runs(p):
            col = _run_color(r)
            if col == str(_RED) and r.font.strike:
                red_strike += 1
            elif col == str(_GREEN):
                green += 1
    ok = red_strike >= 2 and green >= 2
    print(f"\n(c) two-in-one-paragraph: red_strike={red_strike} green={green} "
          f"-> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def check_cross_paragraph_tail():
    """(d) Cross-paragraph match must preserve distinctive trailing text in para 2."""
    tail = "THIS_DISTINCTIVE_TAIL_MUST_SURVIVE_12345"
    p1 = "The Receiving Party agrees to return or dispose of any Information provided by"
    p2 = f"Disclosing Party at its sole discretion. {tail}"
    file_bytes = _mk_doc(["Intro.", p1, p2, "Outro."])
    findings = [{
        "id": "x", "rag_rating": "Amber", "clause_type": "Return of Information",
        "suggested_redline": "return or dispose of any Information provided by Disclosing Party at its sole discretion",
        "replacement_language": "return or dispose of any Information, except routine electronic backups",
        "plain_english_summary": "", "risk_reason": "",
    }]
    gen = DocxDocument(io.BytesIO(generate_issues_report(file_bytes, "t.docx", findings)))
    full = "\n".join("".join(r.text for r in _iter_text_runs(p)) for p in gen.paragraphs)
    ok = tail in full
    print(f"(d) cross-paragraph trailing text preserved: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    fa, fb = check_db()
    fc = check_two_in_one_paragraph()
    fd = check_cross_paragraph_tail()
    failures = fa + fb + fc + fd
    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)
