"""
NDA Synthesis Pipeline v2 — 3 stages:
  Stage 1: Load existing file_manifest.csv (created by v1 — no re-run needed)
  Stage 2: Per-clause batch extraction across all 211 NDAs in groups of 10
           (full NDA text, no character truncation) covering 20 clause types
           with frequency counts, language samples, and entity tier classification
           -> output/v2/batch_summaries_v2.json
  Stage 3: Pre-aggregate batch data in Python, then call Claude Opus 4.8 to
           synthesize an 8-section deterministic decision framework playbook
           -> output/v2/legal_playbook_v2.md

All v2 outputs are checkpointed — re-running resumes from where it left off.
V1 outputs (output/legal_playbook.md) are never touched.

Usage:
  python nda_synthesis_pipeline_v2.py            # run all stages
  python nda_synthesis_pipeline_v2.py --stage 2  # run only Stage 2
  python nda_synthesis_pipeline_v2.py --stage 3  # run only Stage 3
  python nda_synthesis_pipeline_v2.py --repair   # re-run any batch with a parse error
                                                  # (uses 32K output tokens), then re-run Stage 3
  python nda_synthesis_pipeline_v2.py --reset    # delete v2 checkpoints, then run all
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
ROOT           = Path(__file__).parent
ORGANIZED_DIR  = ROOT / "organized"
OUTPUT_V1_DIR  = ROOT / "output"
OUTPUT_V2_DIR  = ROOT / "output" / "v2"
MANIFEST_PATH  = OUTPUT_V1_DIR / "file_manifest.csv"   # reuse v1 manifest
SUMMARIES_PATH = OUTPUT_V2_DIR / "batch_summaries_v2.json"
PLAYBOOK_PATH  = OUTPUT_V2_DIR / "legal_playbook_v2.md"

BATCH_SIZE     = 10     # NDAs per Stage 2 call — full text, no char cap
SONNET_MODEL   = "claude-sonnet-4-6"
OPUS_MODEL     = "claude-opus-4-8"

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
OUTPUT_V2_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — File Discovery (reuse v1 manifest)
# ─────────────────────────────────────────────────────────────────────────────

def stage1() -> list[dict]:
    if not MANIFEST_PATH.exists():
        sys.exit(
            f"ERROR: {MANIFEST_PATH} not found.\n"
            "Run nda_synthesis_pipeline.py first to generate the file manifest."
        )
    print(f"Stage 1: Loading existing manifest from {MANIFEST_PATH.name}")
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"  {len(rows)} files loaded.")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — Per-Clause Batch Extraction
# ─────────────────────────────────────────────────────────────────────────────

_BATCH_PROMPT_V2 = """\
You are an expert NDA analyst. Below are {n} executed NDA agreements signed by Ascential \
Technologies (formerly Burke Porter Group / BPG) and its operating entities. These are real, \
signed agreements representing Ascential's actual negotiating history.

Your task is to extract structured per-clause data for use in building a deterministic AI \
NDA reviewer decision framework. Analyze EVERY clause in EVERY document in this batch.

Return a single JSON object with EXACTLY the schema below. Use integers for all count fields. \
Use verbatim text from the documents for all language fields. If a clause is absent from ALL \
NDAs in this batch, set ndas_with_clause to 0 and leave language fields as empty strings.

ENTITY TIER DEFINITIONS (for the entity_tiers array):
  T1 = Ascential's own BPG/ATHIV standard template returned unchanged by counterparty
  T2 = Counterparty paper with at least one material negotiated change by Ascential,
       OR the same counterparty form has been seen 3+ times across the corpus
  T3 = Counterparty paper, one-off instance, minor or no visible negotiation
  T4 = Counterparty paper accepted wholesale with no visible Ascential pushback

FLOOR vs. PREFERRED language:
  "floor_language" = the weakest language Ascential actually signed in this batch (verbatim)
  "preferred_language" = the strongest / most protective language seen in this batch (verbatim)
  "red_flag_examples" = language that is problematic for Ascential, whether or not it was signed

{{
  "batch_id": {batch_id},
  "files": ["filename1.md"],
  "total_ndas": {n},

  "clause_data": {{

    "confidential_information_definition": {{
      "ndas_with_clause": 0,
      "variants": {{
        "broad_no_marking": 0,
        "marking_required_written_only": 0,
        "marking_with_30day_oral_confirmation": 0,
        "other": 0
      }},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "carve_outs_exceptions": {{
      "ndas_with_clause": 0,
      "carve_out_counts": {{
        "3_standard_only": 0,
        "4_with_independent_development": 0,
        "4_with_third_party_receipt": 0,
        "5_all_standard": 0,
        "6_or_more": 0
      }},
      "has_independent_development": {{"yes": 0, "no": 0}},
      "has_third_party_receipt": {{"yes": 0, "no": 0}},
      "has_legal_compulsion": {{"yes": 0, "no": 0}},
      "has_burden_of_proof_on_recipient": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "recipient_obligations_standard_of_care": {{
      "ndas_with_clause": 0,
      "standard_types": {{
        "reasonably_necessary": 0,
        "same_care_as_own_information": 0,
        "reasonable_care_or_diligence": 0,
        "highest_degree_of_care": 0,
        "other": 0
      }},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "representatives_permitted_disclosures": {{
      "ndas_with_clause": 0,
      "permitted_categories": {{
        "employees": 0, "attorneys": 0, "accountants": 0,
        "financial_advisors": 0, "consultants": 0, "affiliates": 0,
        "financing_sources": 0, "board_members": 0, "other_third_parties": 0
      }},
      "has_vicarious_liability_for_reps": {{"yes": 0, "no": 0}},
      "has_flow_down_obligation_on_reps": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "compelled_disclosure": {{
      "ndas_with_clause": 0,
      "has_prompt_notice_to_discloser": {{"yes": 0, "no": 0}},
      "has_cooperation_for_protective_order": {{"yes": 0, "no": 0}},
      "has_fixed_notice_period": {{"yes": 0, "no": 0}},
      "fixed_notice_examples": [],
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "return_destruction": {{
      "ndas_with_clause": 0,
      "has_archival_backup_carve_out": {{"yes": 0, "no": 0}},
      "has_certification_requirement": {{"yes": 0, "no": 0}},
      "has_reasonable_timeframe": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "term_and_survival": {{
      "ndas_with_clause": 0,
      "term_durations": {{
        "perpetual": 0, "1_year": 0, "2_years": 0, "3_years": 0,
        "4_years": 0, "5_years": 0, "other": 0
      }},
      "has_trade_secret_perpetuity_carve_out": {{"yes": 0, "no": 0}},
      "has_right_to_terminate_unilaterally": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "trade_secret_protection": {{
      "ndas_with_clause": 0,
      "has_dtsa_safe_harbor": {{"yes": 0, "no": 0}},
      "has_perpetual_or_longer_than_term": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "residuals_independent_development": {{
      "ndas_with_clause": 0,
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "reverse_engineering": {{
      "ndas_with_clause": 0,
      "restriction_scope": {{
        "reverse_engineer_only": 0,
        "reverse_engineer_plus_decompile_disassemble": 0,
        "broad_no_derivation_of_source_or_methods": 0
      }},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "injunctive_relief_remedies": {{
      "ndas_with_clause": 0,
      "mutuality": {{
        "mutual_both_parties": 0,
        "one_sided_discloser_only": 0,
        "one_sided_recipient_only": 0,
        "not_specified": 0
      }},
      "has_liquidated_damages": {{"yes": 0, "no": 0}},
      "has_waiver_of_bond_requirement": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "no_license": {{
      "ndas_with_clause": 0,
      "floor_language": "",
      "preferred_language": "",
      "notes": ""
    }},

    "no_representations_warranty": {{
      "ndas_with_clause": 0,
      "floor_language": "",
      "preferred_language": "",
      "notes": ""
    }},

    "governing_law": {{
      "ndas_with_clause": 0,
      "jurisdictions": {{
        "Delaware": 0, "Michigan": 0, "New_York": 0, "California": 0,
        "Illinois": 0, "Wisconsin": 0, "Minnesota": 0, "other_US": 0,
        "non_US": 0
      }},
      "non_us_examples": [],
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "venue_jurisdiction": {{
      "ndas_with_clause": 0,
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "assignment": {{
      "ndas_with_clause": 0,
      "restriction_types": {{
        "no_assignment_without_consent": 0,
        "permitted_on_merger_or_acquisition": 0,
        "unconstrained_assignment_permitted": 0,
        "not_addressed": 0
      }},
      "floor_language": "",
      "preferred_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "non_solicit_non_compete": {{
      "ndas_with_clause": 0,
      "types": {{
        "employee_non_solicit": 0,
        "customer_non_solicit": 0,
        "non_compete": 0
      }},
      "binding_on": {{
        "ascential_only": 0,
        "mutual": 0,
        "counterparty_only": 0
      }},
      "duration_examples": [],
      "floor_language": "",
      "red_flag_examples": [],
      "notes": ""
    }},

    "pe_investor_carve_out": {{
      "ndas_with_clause": 0,
      "explicitly_permits_disclosure_to_investors_lenders": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "notes": ""
    }},

    "export_controls_regulatory_carve_out": {{
      "ndas_with_clause": 0,
      "has_fda_carve_out": {{"yes": 0, "no": 0}},
      "has_iso_carve_out": {{"yes": 0, "no": 0}},
      "has_general_regulatory_carve_out": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "notes": ""
    }},

    "entire_agreement_amendment": {{
      "ndas_with_clause": 0,
      "requires_written_amendment": {{"yes": 0, "no": 0}},
      "floor_language": "",
      "preferred_language": "",
      "notes": ""
    }}

  }},

  "entity_tiers": [
    {{
      "file": "filename.md",
      "tier": "T1",
      "basis": "reason for tier classification"
    }}
  ],

  "negotiated_changes": [
    {{
      "file": "filename.md",
      "clause": "clause type",
      "original_language": "what counterparty originally proposed",
      "final_language": "what was actually signed",
      "significance": "why this change mattered for Ascential"
    }}
  ],

  "batch_red_flags": [
    {{
      "file": "filename.md",
      "clause": "clause type",
      "language": "verbatim problematic language",
      "risk": "specific risk this creates for Ascential"
    }}
  ]
}}

RULES:
- Analyze EVERY document — do not skip any file in the batch.
- Use verbatim language for all language fields — do not paraphrase or summarize.
- Count accurately — every integer must reflect actual occurrences in this batch only.
- Apply entity tier definitions exactly as specified above.
- Return ONLY valid JSON — no markdown fences, no prose outside the JSON object.

{corpus}
"""

_META_PROMPT_V2 = """\
You are a senior NDA counsel at a top-tier US law firm. You have completed a structured \
clause-by-clause analysis of all 211 signed NDA agreements from Ascential Technologies \
(formerly Burke Porter Group / BPG). The data below is the complete per-clause extraction \
across {n_batches} batches covering every one of those {total_ndas} agreements.

Synthesize this data into a definitive Legal Playbook that will be injected verbatim into an \
AI NDA reviewer's system prompt. The AI must use this playbook to make consistent, deterministic \
decisions about every clause it encounters in an inbound NDA, and must use the verbatim language \
from Ascential's real signed agreements when suggesting redlines and replacement language.

The playbook must answer, for every clause type:
1. What did Ascential actually accept in practice — with exact frequency data?
2. What is the decision hierarchy: Preferred → Acceptable → Escalate → Reject?
3. What is the canonical redline language to offer (using verbatim language from the corpus)?
4. How severe is a deviation?

OUTPUT FORMAT: Plain markdown only (##, ###, ####, bullets, **bold**). No JSON. No preamble.
TARGET LENGTH: 4,000–6,000 words. Write densely — every word must carry information.
Write for a lawyer reading at speed: no filler, no hedging, no repetition.
Include ALL verbatim language examples provided in the data — do not compress or summarize them.

Use EXACTLY this 9-section structure:

---

## Ascential Legal Playbook v2 — Deterministic Decision Framework (211 Signed NDAs)

### Section 1 — Corporate Philosophy

[3–5 sentences covering: Ascential's core NDA risk posture; crown jewels = proprietary test \
system designs, automation software, process engineering IP; primary risk = CI definition \
capturing Ascential's own pre-existing IP or independently-developed work; PE-backed under \
AEA Investors = must share with investors and lenders; FDA/ISO 13485/IATF 16949 regulated = \
regulatory carve-outs non-negotiable; engineers work across multiple client engagements = \
residuals protection critical.]

### Section 2 — Universal Non-Negotiables

[5–7 bullets. Items Ascential held consistently across all 211 NDAs regardless of counterparty.
Format each bullet as: **[CRITICAL or HIGH]** — [the rule, grounded in corpus data]
CRITICAL = Ascential should not sign under any circumstances without legal sign-off.
HIGH = Ascential should push back hard; acceptance requires documented business justification.]

### Section 3 — Risk Rating Methodology

[Define four severity levels with specific NDA criteria and action triggers.
Format as a table or structured list:
CRITICAL — [definition, action: must resolve or escalate to Gigi]
HIGH     — [definition, action: push back hard, document if accepted]
MEDIUM   — [definition, action: raise it, accept if counterparty holds firm]
LOW      — [definition, action: note it, Green with comment]
Include: any CRITICAL finding with no viable redline = auto-escalate to Gigi.]

### Section 4 — Clause Standards

[One subsection per clause type. Calculate totals across ALL batches for the frequency line.
Use EXACTLY this format for each subsection:]

#### 4.X [Clause Name]
**Frequency:** X% of 211 NDAs (Y/211). [Key variant breakdown from data.]
**Preferred:** [language Ascential should push for — verbatim from corpus where possible]
**Acceptable (floor):** [worst language Ascential has actually signed — verbatim from corpus]
**Escalate if:** [specific patterns that require legal sign-off before accepting]
**Reject:** [language Ascential should never sign]
**Canonical Redline:** [exact replacement language to offer counterparty, grounded in T1/T2 corpus]
**Fallback:** [minimum acceptable if counterparty rejects canonical redline]
**Deviation severity:** [CRITICAL / HIGH / MEDIUM / LOW]

[Cover all 20 clauses in order:
4.1 Confidential Information Definition
4.2 Carve-outs / Exceptions
4.3 Recipient Obligations / Standard of Care
4.4 Representatives / Permitted Disclosures
4.5 Compelled Disclosure
4.6 Return / Destruction
4.7 Term and Survival
4.8 Trade Secret Protection
4.9 Residuals / Independent Development
4.10 Reverse Engineering
4.11 Injunctive Relief / Remedies
4.12 No License / No Rights Granted
4.13 No Representations / Warranty Disclaimer
4.14 Governing Law
4.15 Venue / Jurisdiction
4.16 Assignment
4.17 Non-Solicitation / Non-Compete
4.18 PE / AEA Investor Carve-out
4.19 Export Controls / Regulatory Disclosure Carve-out
4.20 Entire Agreement / Amendment]

### Section 5 — Entity-Specific Rules and Precedent Tiers

**Precedent tier weighting:**
- **Tier 1 (Most authoritative):** Ascential's own BPG/ATHIV standard template. Do NOT re-flag features of Ascential's own template when it is returned unchanged by a counterparty.
- **Tier 2 (High weight):** [list the specific T2 agreements/counterparties identified in the data]
- **Tier 3 (Medium weight):** One-off counterparty forms with minor or no visible Ascential negotiation.
- **Tier 4 (Low weight — exception, not precedent):** Counterparty paper accepted wholesale. Do not generalize from T4 instances.

[Then: entity-specific patterns for CORP/ATHIV · MLS (Aspect/DKUS/NACS/Korvis) · T&M (Titan/Burke Porter).]

### Section 6 — Industry-Specific Rules

- **Life Sciences (LS):** [2–3 sentences on LS-specific patterns from the data]
- **Automation / Manufacturing (AM):** [2–3 sentences]
- **Instruments & Devices (DEV):** [2–3 sentences]

### Section 7 — Precedent Exceptions (Handle with Care)

[List 8–12 notable below-floor acceptances from the data. For each:]
- **[Counterparty name]** — [clause type]: [what was accepted and why it is below floor]. *Business context unknown — do not treat as general precedent.*

[End the section with: "A Gigi annotation session is required to determine which of the above \
exceptions represent deliberate policy versus one-time commercial concessions. Until that \
session occurs, treat all Tier 4 instances as exceptions, not precedents."]

### Section 8 — Escalation Decision Tree

**Always escalate to Gigi (do not let the rep close):**
[bulleted list of CRITICAL triggers from Sections 2 and 4]

**Escalate only if counterparty refuses the canonical redline:**
[bulleted list of HIGH-severity deviations]

**Rep can handle without escalation:**
- All MEDIUM and LOW severity deviations
- GREEN clauses
- Counterparty accepts canonical redline on any HIGH-severity issue

**Non-NDA provisions — always escalate regardless of counterparty response:**
- Non-solicitation of Ascential employees or customers
- Non-compete obligation binding on Ascential
- IP assignment or licensing grant
- Exclusivity or standstill obligation
- Rights of first refusal or most-favoured-nation clause
- Arbitration clause governing disputes beyond confidentiality

### Section 9 — Canonical Language Library

[This section is the verbatim language reference for the AI reviewer.  For EVERY one of the
20 clause types in Section 4, provide the following — using VERBATIM text pulled from the
floor_examples and preferred_examples in the corpus data:

#### 9.X [Clause Name]
**Ascential's preferred language (most protective — from T1/T2 corpus):**
> [verbatim quote from preferred_examples, exactly as it appears in signed NDAs]

**Acceptable floor language (weakest Ascential has signed):**
> [verbatim quote from floor_examples, exactly as it appears in signed NDAs]

**Canonical redline sentence (use this exact text when suggesting a replacement):**
> [a single sentence Ascential should propose as a redline, grounded in the preferred language above]

Include ALL distinct preferred and floor examples from the data — do not select just one.
If multiple variants exist, list each on a separate line starting with >.
If a clause type has no examples in the corpus, write "No verbatim examples in corpus — use
Ascential's standard template form."

The AI reviewer MUST use the canonical redline sentence as its replacement_language suggestion
whenever it flags that clause type.  This ensures all AI output uses actual Ascential contract
language, not AI-generated paraphrase.]

---

HERE IS THE PRE-AGGREGATED DATA from {n_batches} batches covering {total_ndas} NDAs:

{summaries}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_CLAUSE_KEYS = [
    "confidential_information_definition",
    "carve_outs_exceptions",
    "recipient_obligations_standard_of_care",
    "representatives_permitted_disclosures",
    "compelled_disclosure",
    "return_destruction",
    "term_and_survival",
    "trade_secret_protection",
    "residuals_independent_development",
    "reverse_engineering",
    "injunctive_relief_remedies",
    "no_license",
    "no_representations_warranty",
    "governing_law",
    "venue_jurisdiction",
    "assignment",
    "non_solicit_non_compete",
    "pe_investor_carve_out",
    "export_controls_regulatory_carve_out",
    "entire_agreement_amendment",
]


def _sum_nested(target: dict, source: dict) -> None:
    """Recursively sum integer values from source into target."""
    for k, v in source.items():
        if isinstance(v, int):
            target[k] = target.get(k, 0) + v
        elif isinstance(v, dict):
            if k not in target:
                target[k] = {}
            _sum_nested(target[k], v)


def _aggregate_summaries(summaries: list[dict]) -> dict:
    """
    Pre-aggregate batch summaries into a compact representation for Stage 3.
    Reduces Stage 3 input from ~220K tokens to ~20K tokens by:
    - Summing frequency counts across all clean batches
    - Keeping up to 3 distinct floor/preferred language examples per clause
    - Keeping up to 5 distinct red-flag examples per clause
    - Collecting all negotiated_changes and batch_red_flags (capped)
    Batches with _parse_error are excluded and listed separately.
    """
    total_ndas = sum(s.get("total_ndas", len(s.get("files", []))) for s in summaries)
    clean = [s for s in summaries if "_parse_error" not in s]
    failed_ids = [s.get("batch_id") for s in summaries if "_parse_error" in s]

    clause_totals: dict[str, dict] = {}
    notable_language: dict[str, dict] = {}

    for key in _CLAUSE_KEYS:
        counts: dict = {}
        floors: list[str] = []
        prefs: list[str] = []
        flags: list[str] = []

        for s in clean:
            clause = s.get("clause_data", {}).get(key, {})
            if not clause:
                continue
            _sum_nested(counts, {k: v for k, v in clause.items()
                                  if isinstance(v, (int, dict))})
            fl = clause.get("floor_language", "")
            pf = clause.get("preferred_language", "")
            if fl and fl not in floors:
                floors.append(fl)
            if pf and pf not in prefs:
                prefs.append(pf)
            for r in clause.get("red_flag_examples", []):
                if r and r not in flags:
                    flags.append(r)

        clause_totals[key] = {
            "total_ndas_with_clause": counts.get("ndas_with_clause", 0),
            "frequency_pct": (
                round(counts.get("ndas_with_clause", 0) / total_ndas * 100, 1)
                if total_ndas else 0
            ),
            "aggregated_counts": {k: v for k, v in counts.items()
                                   if k != "ndas_with_clause"},
        }
        notable_language[key] = {
            "floor_examples": floors[:10],
            "preferred_examples": prefs[:10],
            "red_flag_examples": flags[:10],
        }

    # Entity tiers — deduplicated by file
    seen: set[str] = set()
    entity_tiers: list[dict] = []
    for s in clean:
        for t in s.get("entity_tiers", []):
            if t.get("file") not in seen:
                seen.add(t.get("file", ""))
                entity_tiers.append(t)

    negotiated_changes: list[dict] = []
    red_flags: list[dict] = []
    for s in clean:
        negotiated_changes.extend(s.get("negotiated_changes", []))
        red_flags.extend(s.get("batch_red_flags", []))

    return {
        "total_ndas": total_ndas,
        "clean_batches": len(clean),
        "failed_batches_excluded": failed_ids,
        "clause_totals": clause_totals,
        "notable_language": notable_language,
        "entity_tiers": entity_tiers[:120],
        "negotiated_changes": negotiated_changes[:60],
        "red_flags": red_flags[:60],
    }


def _build_corpus_v2(file_paths: list[Path]) -> tuple[str, list[str]]:
    """Full-text corpus — no character truncation."""
    parts, names = [], []
    for fp in file_paths:
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not text:
            continue
        parts.append(f"\n\n{'='*60}\nFILE: {fp.name}\n{'='*60}\n{text}")
        names.append(fp.name)
    return "".join(parts), names


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[^\n]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    return raw.strip()


def _run_batch(batch_id: int, batch_files: list[Path], names: list[str],
               max_tokens: int = 16_000) -> dict:
    corpus, _ = _build_corpus_v2(batch_files)
    prompt = _BATCH_PROMPT_V2.format(n=len(batch_files), batch_id=batch_id, corpus=corpus)
    try:
        # Use streaming for large token budgets to avoid the 10-minute timeout limit
        if max_tokens > 16_000:
            with client.messages.stream(
                model=SONNET_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                response = stream.get_final_message()
        else:
            response = client.messages.create(
                model=SONNET_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        raw = _strip_fences(response.content[0].text)
    except Exception as e:
        print(f"\n    [ERROR] API call failed for batch {batch_id}: {e}")
        time.sleep(15)
        return {"batch_id": batch_id, "files": names, "_api_error": str(e)}

    try:
        summary = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\n    [WARN] JSON parse error in batch {batch_id}: {e}")
        return {"batch_id": batch_id, "files": names, "_parse_error": raw[:500]}

    summary["batch_id"] = batch_id
    if "files" not in summary:
        summary["files"] = names
    return summary


def stage2(rows: list[dict]) -> list[dict]:
    all_paths = [Path(r["file_path"]) for r in rows]
    print(f"Stage 2: Processing {len(all_paths)} files in batches of {BATCH_SIZE} "
          f"(full NDA text, no truncation)...")

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
        _, names = _build_corpus_v2(batch_files)
        summary = _run_batch(batch_id, batch_files, names)
        existing[batch_id] = summary

        SUMMARIES_PATH.write_text(
            json.dumps(list(existing.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("done.")
        time.sleep(1)

    all_summaries = [existing[i] for i in sorted(existing)]
    print(f"  Stage 2 complete: {n_total} batches -> {SUMMARIES_PATH}")
    return all_summaries


def repair_failed_batches(rows: list[dict]) -> list[dict]:
    """Re-run any batch saved with _parse_error using 32K output tokens."""
    if not SUMMARIES_PATH.exists():
        sys.exit("No batch_summaries_v2.json found — run Stage 2 first.")

    existing: dict[int, dict] = {}
    for entry in json.loads(SUMMARIES_PATH.read_text(encoding="utf-8")):
        existing[int(entry["batch_id"])] = entry

    failed_ids = [bid for bid, s in existing.items()
                  if "_parse_error" in s or "_api_error" in s]
    if not failed_ids:
        print("Repair: No failed batches found — nothing to do.")
        return [existing[i] for i in sorted(existing)]

    print(f"Repair: Re-running {len(failed_ids)} failed batch(es) with 32K output tokens: "
          f"{[b + 1 for b in failed_ids]}")

    all_paths = [Path(r["file_path"]) for r in rows]
    batches = [all_paths[i: i + BATCH_SIZE] for i in range(0, len(all_paths), BATCH_SIZE)]

    for batch_id in failed_ids:
        batch_files = batches[batch_id]
        print(f"  Re-running batch {batch_id + 1}: {len(batch_files)} NDAs...", end=" ", flush=True)
        _, names = _build_corpus_v2(batch_files)
        summary = _run_batch(batch_id, batch_files, names, max_tokens=32_000)
        existing[batch_id] = summary
        SUMMARIES_PATH.write_text(
            json.dumps(list(existing.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("done.")
        time.sleep(1)

    still_failed = [bid + 1 for bid, s in existing.items()
                    if "_parse_error" in s or "_api_error" in s]
    if still_failed:
        print(f"  [WARN] These batches still have parse errors after repair: {still_failed}")
    else:
        print("  All batches clean.")

    return [existing[i] for i in sorted(existing)]


def stage3(summaries: list[dict], force: bool = False) -> None:
    if not force and PLAYBOOK_PATH.exists() and PLAYBOOK_PATH.stat().st_size > 100:
        print(f"Stage 3: {PLAYBOOK_PATH.name} already exists — skipping. Use --stage 3 --regen to force.")
        return

    total_ndas = sum(s.get("total_ndas", len(s.get("files", []))) for s in summaries)
    n_clean = sum(1 for s in summaries if "_parse_error" not in s)
    print(
        f"Stage 3: Aggregating {n_clean}/{len(summaries)} clean batches "
        f"({total_ndas} total NDAs) then synthesizing..."
    )

    agg = _aggregate_summaries(summaries)
    agg_json = json.dumps(agg, indent=1, ensure_ascii=False)
    est_tokens = len(agg_json) // 4
    print(f"  Aggregated input size: ~{est_tokens:,} tokens (was ~{222_000:,} raw)")

    if agg["failed_batches_excluded"]:
        print(f"  [WARN] {len(agg['failed_batches_excluded'])} batches excluded "
              f"(parse errors): {[b + 1 for b in agg['failed_batches_excluded']]}. "
              f"Run --repair first for best results.")

    prompt = _META_PROMPT_V2.format(
        n_batches=len(summaries),
        total_ndas=total_ndas,
        summaries=agg_json,
    )

    print("  Calling Claude Opus 4.8 with adaptive thinking (120–240 seconds)...", flush=True)
    with client.messages.stream(
        model=OPUS_MODEL,
        max_tokens=32_000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()
    playbook = next(
        (block.text for block in response.content if block.type == "text"), ""
    ).strip()

    if not playbook:
        print("  [ERROR] Opus returned no text output — check token budget.")
        return

    PLAYBOOK_PATH.write_text(playbook, encoding="utf-8")
    word_count = len(playbook.split())
    print(f"  Stage 3 complete: ~{word_count} words -> {PLAYBOOK_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NDA Synthesis Pipeline v2")
    parser.add_argument(
        "--stage", type=int, choices=[1, 2, 3],
        help="Run only a specific stage (default: all)",
    )
    parser.add_argument(
        "--regen", action="store_true",
        help="Force Stage 3 to re-run even if legal_playbook_v2.md already exists.",
    )
    parser.add_argument(
        "--repair", action="store_true",
        help="Re-run any batch with a parse error using 32K output tokens, "
             "then re-run Stage 3.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete v2 checkpoints (batch_summaries_v2.json and legal_playbook_v2.md) "
             "before running. Does NOT touch v1 outputs.",
    )
    args = parser.parse_args()

    if args.reset:
        for p in (SUMMARIES_PATH, PLAYBOOK_PATH):
            if p.exists():
                p.unlink()
                print(f"  Deleted: {p.name}")

    rows = stage1()

    if args.repair:
        summaries = repair_failed_batches(rows)
        # Delete empty or stale playbook so Stage 3 re-runs
        if PLAYBOOK_PATH.exists():
            PLAYBOOK_PATH.unlink()
            print(f"  Deleted stale: {PLAYBOOK_PATH.name}")
        stage3(summaries)
        print("\nDone.")
        return

    run_stages = [args.stage] if args.stage else [1, 2, 3]

    summaries: list[dict] = []
    if 2 in run_stages:
        summaries = stage2(rows)
    elif 3 in run_stages:
        if not SUMMARIES_PATH.exists():
            sys.exit(
                "Run Stage 2 first: python nda_synthesis_pipeline_v2.py --stage 2"
            )
        summaries = json.loads(SUMMARIES_PATH.read_text(encoding="utf-8"))

    if 3 in run_stages:
        stage3(summaries, force=args.regen)

    print("\nDone.")


if __name__ == "__main__":
    main()
