"""
NDA Synthesis Pipeline — 3 stages:
  Stage 1: Discover all NDA markdown files, parse metadata from directory structure
           and filenames -> output/file_manifest.csv
  Stage 2: Batch-extract clause patterns across all NDAs in groups of 20
           (~11 Claude Sonnet calls total) -> output/batch_summaries.json
  Stage 3: Meta-synthesize all batch summaries into a compact legal playbook
           (1 Claude Opus call) -> output/legal_playbook.md

All outputs are checkpointed — re-running resumes from where it left off.
Usage:
  python nda_synthesis_pipeline.py            # run all stages
  python nda_synthesis_pipeline.py --stage 2  # run only Stage 2
  python nda_synthesis_pipeline.py --reset    # delete all checkpoints, then run all
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
ROOT            = Path(__file__).parent
ORGANIZED_DIR   = ROOT / "organized"
OUTPUT_DIR      = ROOT / "output"
MANIFEST_PATH   = OUTPUT_DIR / "file_manifest.csv"
SUMMARIES_PATH  = OUTPUT_DIR / "batch_summaries.json"
PLAYBOOK_PATH   = OUTPUT_DIR / "legal_playbook.md"

BATCH_SIZE        = 20       # NDAs per Stage 2 API call
MAX_CHARS_PER_NDA = 6_000    # per-file cap to keep each batch under ~30K tokens
SONNET_MODEL      = "claude-sonnet-4-6"
OPUS_MODEL        = "claude-opus-4-8"

# ── API client ────────────────────────────────────────────────────────────────
_env_path = ROOT / "backend" / ".env"
_api_key = None
for _line in _env_path.read_text(encoding="utf-8").splitlines():
    if _line.startswith("ANTHROPIC_API_KEY="):
        _api_key = _line.split("=", 1)[1].strip()
        break
if not _api_key:
    sys.exit("ERROR: ANTHROPIC_API_KEY not found in backend/.env")

client = anthropic.Anthropic(api_key=_api_key)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Filename / path parsing ───────────────────────────────────────────────────
_DATE_RE = re.compile(r"\b(\d{1,2}[A-Za-z]{3}\d{2,4}|\d{2}[A-Za-z]{3}\d{4})\b")


def _parse_file(file_path: Path) -> dict:
    """
    Extract structured metadata from a file's directory path and stem.
    The directory structure (BU / NDA-type / entity-context) is the authoritative
    source; the filename is parsed for counterparty and date.
    """
    rel = file_path.relative_to(ORGANIZED_DIR)
    dir_parts = rel.parts[:-1]  # e.g. ('CORP', 'MNDA', 'ATHIV')

    row = {
        "file_path": str(file_path),
        "business_unit":          dir_parts[0] if len(dir_parts) > 0 else "",
        "nda_type":               dir_parts[1] if len(dir_parts) > 1 else "",
        "entity_or_specialization": dir_parts[2] if len(dir_parts) > 2 else "",
        "counterparty": "",
        "date": "",
        "parse_error": "False",
    }

    stem = file_path.stem
    # Date: find the last date-like token in the stem
    date_match = _DATE_RE.search(stem)
    row["date"] = date_match.group(1) if date_match else ""

    # Counterparty: the filename usually encodes counterparty between the last
    # known entity token and the date.  Use a simple heuristic: take everything
    # after the 4th dash-separated segment and before the date.
    segments = [s.strip() for s in stem.split("-") if s.strip()]
    if len(segments) >= 5:
        # Join the middle segments and strip date / trailing modifiers
        candidate = "-".join(segments[4:])
        if date_match:
            candidate = candidate[: candidate.find(date_match.group(1))].strip(" -")
        candidate = re.sub(r"\s*(signed|draft|endorsed|amendment|amend|v\d+)\s*$",
                           "", candidate, flags=re.IGNORECASE).strip()
        row["counterparty"] = candidate
    elif not row["business_unit"]:
        row["parse_error"] = "True"

    return row


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — File Discovery
# ─────────────────────────────────────────────────────────────────────────────

def stage1() -> list[dict]:
    if MANIFEST_PATH.exists():
        print(f"Stage 1: {MANIFEST_PATH.name} already exists — loading.")
        with MANIFEST_PATH.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    print("Stage 1: Discovering NDA files...")
    all_files = sorted(ORGANIZED_DIR.rglob("*.md"))
    if not all_files:
        sys.exit(f"ERROR: No markdown files found under {ORGANIZED_DIR}")
    print(f"  Found {len(all_files)} markdown files")

    rows = [_parse_file(f) for f in all_files]
    errors = sum(1 for r in rows if r["parse_error"] == "True")
    if errors:
        print(f"  [WARN] {errors} files could not be fully parsed (flagged in CSV)")

    fieldnames = ["file_path", "business_unit", "nda_type", "entity_or_specialization",
                  "counterparty", "date", "parse_error"]
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Stage 1 complete: {len(rows)} files -> {MANIFEST_PATH}")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — Batch Clause Extraction
# ─────────────────────────────────────────────────────────────────────────────

_BATCH_PROMPT = """\
You are an expert NDA analyst. Below are {n} executed NDA agreements signed by Ascential \
Technologies (formerly Burke Porter Group / BPG) and its operating entities. These are real, \
signed agreements representing Ascential's actual negotiating history.

Extract structured knowledge for use in calibrating an AI NDA reviewer. Analyze ALL documents \
in this batch and return a single JSON object with EXACTLY these keys:

{{
  "batch_id": {batch_id},
  "files": ["filename1.md", ...],
  "accepted_language_samples": [
    {{
      "clause_type": "e.g. Residuals / Independent Development",
      "language": "verbatim or near-verbatim clause text Ascential accepted",
      "entity_context": "CORP/ATHIV, MLS-DKUS, MLS-NACS, etc.",
      "notes": "why notable (accepted despite being weaker than ideal, etc.)"
    }}
  ],
  "negotiated_changes": [
    {{
      "clause_type": "e.g. Governing Law",
      "original_language": "what the counterparty originally proposed",
      "accepted_form": "what was actually signed",
      "notes": "why the change mattered"
    }}
  ],
  "governing_law_observed": ["list of states/jurisdictions seen"],
  "term_durations_observed": ["e.g. '3 years', 'perpetual', '2 years from effective date'"],
  "entity_observations": {{
    "CORP_ATHIV":   "patterns specific to BPG Holdings / ATHIV entity NDAs",
    "MLS_DKUS":     "D&K Engineering patterns (if files present)",
    "MLS_NACS":     "NACS patterns (if files present)",
    "MLS_KORVIS":   "Korvis patterns (if files present)",
    "TM_Titan":     "Titan / T&M patterns (if files present)",
    "other":        "anything that does not fit above"
  }},
  "red_flags_in_batch": [
    {{
      "clause_type": "e.g. Assignment",
      "language": "verbatim problematic language from the document",
      "concern": "specific risk this creates for Ascential"
    }}
  ],
  "specialization_patterns": {{
    "life_sciences_LS":    "LS / medical device NDA patterns seen in this batch",
    "automation_AM":       "automation / manufacturing patterns seen",
    "instruments_DEV":     "instruments & devices patterns seen"
  }},
  "notable_carve_outs": "summary of which of the 5 standard carve-outs were present / absent across this batch",
  "non_solicit_non_compete": "any non-solicitation or non-compete clauses observed, with entity context"
}}

RULES:
- Base every answer strictly on the documents provided — never invent examples.
- Include verbatim language wherever possible; reviewers will use this to calibrate.
- If a key has nothing to report for this batch, use an empty string or empty array.
- Return ONLY valid JSON — no markdown fences, no prose outside the JSON object.

{corpus}
"""


def _build_corpus(file_paths: list[Path]) -> tuple[str, list[str]]:
    parts, names = [], []
    for fp in file_paths:
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not text:
            continue
        text = text[:MAX_CHARS_PER_NDA]
        parts.append(f"\n\n{'='*60}\nFILE: {fp.name}\n{'='*60}\n{text}")
        names.append(fp.name)
    return "".join(parts), names


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[^\n]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    return raw.strip()


def stage2(rows: list[dict]) -> list[dict]:
    all_paths = [Path(r["file_path"]) for r in rows]
    print(f"Stage 2: Processing {len(all_paths)} files in batches of {BATCH_SIZE}...")

    # Load checkpoint
    existing: dict[int, dict] = {}
    if SUMMARIES_PATH.exists():
        try:
            for entry in json.loads(SUMMARIES_PATH.read_text(encoding="utf-8")):
                existing[int(entry["batch_id"])] = entry
        except Exception:
            pass

    batches = [all_paths[i: i + BATCH_SIZE] for i in range(0, len(all_paths), BATCH_SIZE)]
    n_total = len(batches)

    for batch_id, batch_files in enumerate(batches):
        if batch_id in existing:
            print(f"  Batch {batch_id + 1}/{n_total}: already done — skipping.")
            continue

        print(f"  Batch {batch_id + 1}/{n_total}: {len(batch_files)} NDAs...", end=" ", flush=True)
        corpus, names = _build_corpus(batch_files)

        prompt = _BATCH_PROMPT.format(
            n=len(batch_files),
            batch_id=batch_id,
            corpus=corpus,
        )

        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=16_000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _strip_fences(response.content[0].text)

        try:
            summary = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"\n    [WARN] JSON parse error in batch {batch_id}: {e}")
            summary = {"batch_id": batch_id, "files": names, "_parse_error": raw[:300]}

        summary["batch_id"] = batch_id
        if "files" not in summary:
            summary["files"] = names
        existing[batch_id] = summary

        # Checkpoint after every batch
        SUMMARIES_PATH.write_text(
            json.dumps(list(existing.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("done.")
        time.sleep(1)  # avoid rate-limit bursts

    all_summaries = [existing[i] for i in sorted(existing)]
    print(f"  Stage 2 complete: {n_total} batches -> {SUMMARIES_PATH}")
    return all_summaries


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — Meta-Synthesis -> legal_playbook.md
# ─────────────────────────────────────────────────────────────────────────────

_META_PROMPT = """\
You are a senior NDA counsel synthesizing institutional knowledge from Ascential Technologies' \
211 signed NDA agreements. I will give you structured extractions from {n_batches} batches \
covering all 211 documents. Synthesize these into a compact Legal Playbook that will be injected \
verbatim into an AI NDA reviewer's system prompt on every review call.

REQUIREMENTS:
- Target 500–750 tokens (approximately 375–560 words). Terse and precise.
- Plain markdown only: headers (##, ###), bullet points, **bold** for emphasis.
- Every bullet must be grounded in the extraction data — no invented examples.
- Use specific clause language from the extractions where it adds precision.
- Write for a lawyer reading at speed: no preamble, no filler sentences.
- Output ONLY the markdown content — no JSON, no prose before or after the playbook.

OUTPUT STRUCTURE (use exactly these five sections, in order):

## Ascential Legal Playbook — Institutional Knowledge from 211 Signed NDAs

### Universal Non-Negotiables (Held Across All Entities)
[4–6 bullet points: what Ascential consistently required or refused to waive,
drawn from patterns seen across the full corpus]

### Entity-Specific Standards
[Sub-bullets grouped by entity: CORP/ATHIV · MLS (DKUS/NACS/KORVIS) · TM/Titan.
1–3 bullets per entity covering what differs from the universal standard.
Omit an entity if no distinct pattern was observed.]

### Acceptable Fallback Positions (Ascential Has Signed These)
[4–6 bullet points: terms weaker than ideal that Ascential nonetheless accepted.
This is the floor — the AI reviewer should flag anything below this as unacceptable.]

### Consistent Red Flags (Ascential Pushed Back On These)
[4–5 bullet points: specific clause types or language Ascential's attorneys
consistently rejected, with verbatim example language where available.]

### Preferred Language Patterns by Specialization
- **Life Sciences (LS):** [1–2 sentences]
- **Automation / Manufacturing (AM):** [1–2 sentences]
- **Instruments & Devices (DEV):** [1–2 sentences]

HERE ARE THE BATCH EXTRACTIONS:

{summaries}
"""


def stage3(summaries: list[dict]) -> None:
    if PLAYBOOK_PATH.exists():
        print(f"Stage 3: {PLAYBOOK_PATH.name} already exists — skipping.")
        return

    print(f"Stage 3: Synthesizing {len(summaries)} batch summaries into legal_playbook.md...")

    summaries_json = json.dumps(summaries, indent=1, ensure_ascii=False)
    if len(summaries_json) > 80_000:
        summaries_json = summaries_json[:80_000] + "\n... [truncated for length]"

    prompt = _META_PROMPT.format(n_batches=len(summaries), summaries=summaries_json)

    print("  Calling Claude Opus 4.8 (may take 60–120 seconds)...", flush=True)
    response = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=4_000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )
    playbook = next(
        (block.text for block in response.content if block.type == "text"), ""
    ).strip()

    PLAYBOOK_PATH.write_text(playbook, encoding="utf-8")
    word_count = len(playbook.split())
    print(f"  Stage 3 complete: ~{word_count} words -> {PLAYBOOK_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NDA Synthesis Pipeline")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3],
                        help="Run only a specific stage (default: all)")
    parser.add_argument("--reset", action="store_true",
                        help="Delete all checkpoints before running")
    args = parser.parse_args()

    if args.reset:
        for p in (MANIFEST_PATH, SUMMARIES_PATH, PLAYBOOK_PATH):
            if p.exists():
                p.unlink()
                print(f"  Deleted: {p.name}")

    run_stages = [args.stage] if args.stage else [1, 2, 3]

    rows = stage1() if 1 in run_stages else (
        list(csv.DictReader(MANIFEST_PATH.open(encoding="utf-8")))
        if MANIFEST_PATH.exists() else sys.exit("Run Stage 1 first.")
    )

    summaries: list[dict] = []
    if 2 in run_stages:
        summaries = stage2(rows)
    elif 3 in run_stages:
        if not SUMMARIES_PATH.exists():
            sys.exit("Run Stage 2 first.")
        summaries = json.loads(SUMMARIES_PATH.read_text(encoding="utf-8"))

    if 3 in run_stages:
        stage3(summaries)

    print("\nDone.")


if __name__ == "__main__":
    main()
