# Synthesize Ascential NDA patterns from 211 converted historical NDAs.
# Samples ~25 representative files across all three categories, sends them to
# Claude Opus 4.8 in one call, and outputs a JSON file with:
#   - Standard Ascential template clause language (verbatim key phrases)
#   - Historical accepted parameter ranges
#   - Common counterparty patterns / deviations that have been signed
# The output is then injected into the system prompt in claude_service.py.

import json
import random
import sys
from pathlib import Path

import anthropic

# ── Config ─────────────────────────────────────────────────────────────────
REFERENCE_DIR = Path(r"C:\Claude\Projects\NDA Reviewer\reference_ndas")
OUTPUT_FILE   = Path(r"C:\Claude\Projects\NDA Reviewer\backend\nda_knowledge.json")
SAMPLE_SIZE   = 25       # files to include (spread across categories)
MAX_CHARS_PER = 6000     # cap per NDA to control total token cost
TOTAL_CAP     = 120_000  # total chars fed to Claude (~30k tokens of NDA text)

# Read API key from backend .env
env_path = Path(r"C:\Claude\Projects\NDA Reviewer\backend\.env")
api_key  = None
for line in env_path.read_text().splitlines():
    if line.startswith("ANTHROPIC_API_KEY="):
        api_key = line.split("=", 1)[1].strip()
        break
if not api_key:
    sys.exit("ERROR: could not read ANTHROPIC_API_KEY from backend/.env")

client = anthropic.Anthropic(api_key=api_key)

# ── Sample NDAs ─────────────────────────────────────────────────────────────
all_files = list(REFERENCE_DIR.rglob("*.md"))
print(f"Total converted NDAs available: {len(all_files)}")

# Prefer recent, larger files (more content); spread across categories
by_category: dict[str, list[Path]] = {}
for f in all_files:
    cat = f.relative_to(REFERENCE_DIR).parts[0]
    by_category.setdefault(cat, []).append(f)

per_cat = max(1, SAMPLE_SIZE // len(by_category))
sample: list[Path] = []
for cat, files in by_category.items():
    # sort by file size descending (more content = more valuable)
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    sample.extend(files[:per_cat])

# top up to SAMPLE_SIZE from remaining large files
remaining = [f for f in all_files if f not in sample]
remaining.sort(key=lambda p: p.stat().st_size, reverse=True)
sample.extend(remaining[: SAMPLE_SIZE - len(sample)])
sample = sample[:SAMPLE_SIZE]

print(f"Sampled {len(sample)} NDAs for analysis")

# ── Build corpus text ────────────────────────────────────────────────────────
corpus_parts = []
total = 0
for f in sample:
    text = f.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        continue
    text = text[:MAX_CHARS_PER]
    header = f"\n\n{'='*70}\nFILE: {f.relative_to(REFERENCE_DIR)}\n{'='*70}\n"
    corpus_parts.append(header + text)
    total += len(text)
    if total >= TOTAL_CAP:
        break

corpus = "".join(corpus_parts)
print(f"Total characters fed to Claude: {len(corpus):,}")

# ── Synthesis prompt ─────────────────────────────────────────────────────────
SYNTHESIS_PROMPT = """You are a specialist NDA analyst. I am going to give you a corpus of
historical NDA agreements that Ascential Technologies (formerly Burke Porter Group / BPG)
has signed with various counterparties. Your task is to extract structured knowledge that
will be used to improve an AI-powered NDA review tool.

Analyze ALL documents in the corpus and produce a JSON object with EXACTLY these keys:

{
  "ascential_template_clauses": {
    "description": "Verbatim or near-verbatim key phrases from Ascential's OWN standard template (the BPG/Titan form). Include the exact wording of the most important clauses so a reviewer can recognise when a counterparty is returning Ascential's own paper vs. presenting their own form.",
    "confidential_information_definition": "...",
    "carve_outs": "...",
    "term_and_survival": "...",
    "permitted_disclosure": "...",
    "return_of_materials": "...",
    "injunctive_relief": "...",
    "governing_law": "...",
    "burden_of_proof": "..."
  },
  "historical_accepted_ranges": {
    "description": "Ranges of key parameters that Ascential has actually signed in real agreements",
    "confidentiality_term_years": {"min": null, "max": null, "most_common": null, "notes": ""},
    "survival_after_termination": {"observations": ""},
    "governing_law_states": [],
    "non_solicit_duration_years": {"observations": ""},
    "carve_outs_present": {"notes": ""}
  },
  "common_counterparty_patterns": [
    {
      "pattern": "Short description of a recurring clause type or deviation",
      "counterparty_language": "Typical wording used by counterparties",
      "ascential_accepted": true,
      "notes": "What to watch for / when it becomes a problem"
    }
  ],
  "red_flags_seen_in_real_agreements": [
    {
      "clause_type": "...",
      "example_language": "...",
      "why_problematic": "..."
    }
  ],
  "entity_naming_observations": "Any observations about how Ascential entities are named in these agreements — correct vs. incorrect usage seen in the corpus"
}

IMPORTANT:
- Base every answer strictly on the documents provided — do not invent examples.
- For ascential_template_clauses, use the most commonly appearing verbatim language you find.
- For historical_accepted_ranges, only state what you actually observe in the corpus.
- Return ONLY valid JSON — no markdown fences, no prose outside the JSON object.

Here is the NDA corpus:

""" + corpus

# ── Call Claude ───────────────────────────────────────────────────────────────
print("\nSending to Claude Opus 4.8 for synthesis (this may take 30-60 seconds)...")
response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=8000,
    thinking={"type": "adaptive"},
    messages=[{"role": "user", "content": SYNTHESIS_PROMPT}],
)

raw = next(
    (block.text for block in response.content if block.type == "text"),
    ""
).strip()

# Strip fences if any
if raw.startswith("```"):
    import re
    raw = re.sub(r"^```[^\n]*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)

# Parse
try:
    knowledge = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"\nJSON parse error: {e}")
    print("Raw output saved to nda_knowledge_raw.txt for inspection")
    Path("nda_knowledge_raw.txt").write_text(raw, encoding="utf-8")
    sys.exit(1)

# Save
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.write_text(json.dumps(knowledge, indent=2), encoding="utf-8")
print(f"\nDone. Knowledge file saved to: {OUTPUT_FILE}")
print("\nKey findings:")
if "historical_accepted_ranges" in knowledge:
    r = knowledge["historical_accepted_ranges"]
    print(f"  Confidentiality term: {r.get('confidentiality_term_years', {})}")
    print(f"  Governing law states: {r.get('governing_law_states', [])}")
if "common_counterparty_patterns" in knowledge:
    print(f"  Counterparty patterns identified: {len(knowledge['common_counterparty_patterns'])}")
if "red_flags_seen_in_real_agreements" in knowledge:
    print(f"  Real red flags catalogued: {len(knowledge['red_flags_seen_in_real_agreements'])}")
