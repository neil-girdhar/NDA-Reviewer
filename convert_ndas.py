# One-time script: convert Ascential historical NDA PDFs to Markdown
# Output: C:/Claude/Projects/NDA Reviewer/reference_ndas/
# Preserves the three source category folders as subfolders.
from pathlib import Path
from markitdown import MarkItDown

INPUT_ROOT  = Path(r"C:\Users\neil.girdhar\Downloads\NDA_Zip_Extract")
OUTPUT_ROOT = Path(r"C:\Claude\Projects\NDA Reviewer\reference_ndas")

md = MarkItDown()
ok = fail = skip = 0

for pdf in sorted(INPUT_ROOT.rglob("*.pdf")):
    # Preserve category subfolder (first level under INPUT_ROOT)
    rel   = pdf.relative_to(INPUT_ROOT)
    parts = rel.parts
    category = parts[0]          # e.g. "Corporate"
    dest_dir  = OUTPUT_ROOT / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / (pdf.stem + ".md")
    if dest.exists():
        skip += 1
        continue

    try:
        result = md.convert(str(pdf))
        text   = result.text_content.strip()
        if not text:
            print(f"  EMPTY  {rel}")
            fail += 1
            continue
        dest.write_text(text, encoding="utf-8")
        print(f"  OK     {rel}")
        ok += 1
    except Exception as e:
        print(f"  FAIL   {rel}  →  {e}")
        fail += 1

print(f"\n{'='*60}")
print(f"Done.  OK: {ok}   Skipped (already exist): {skip}   Failed: {fail}")
print(f"Output: {OUTPUT_ROOT}")
