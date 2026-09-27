from pathlib import Path
import json

import pymupdf as fitz
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "verification" / "chip-tips-v15-sample.pdf"
OUT = ROOT / "verification"

reader = PdfReader(str(PDF))
assert len(reader.pages) == 3, f"expected 3 sheets, got {len(reader.pages)}"
text = "\n".join(page.extract_text() or "" for page in reader.pages)
verified_values = [
    "Shared Guest", "Window Guest", "256", "257",
    "$20.00", "$10.00", "$30.00", "$2,448.00", "$2,478.00",
]
for title in ["CLUB DANCE DOLLAR TIPS", "SUPERVISOR TAB TOTALS", "CAGE SMARTTAB TIP TOTALS", "CHIP TOTALS SHEET"]:
    assert title in text, title
for value in verified_values:
    assert value in text, value
# The check number and the customer tip are typed once and printed on both the tip
# sheet and the Chip Totals sheet, so each appears on more than one page.
assert text.count("256") >= 2, "the check number must reach the Chip Totals tab column"
assert text.count("257") >= 2, "the check number must reach the Chip Totals tab column"
# The separate tab numbers and SmartTab tips that older chip rows carried are gone,
# because they are the same values as the check number and the customer tip.
for stale in ["124.80", "364.80"]:
    assert stale not in text, f"unpaired SmartTab tip {stale} still printed"
assert '"tipRows"' not in text
assert text.count("PEPPERMINT HIPPO") == 3
assert text.count("LAS VEGAS") == 3
# The "Prev Pg" / "PRIOR PG" carry-forward row is obsolete now that a multi-page
# shift prints every page in one pass, so it must be fully gone from every sheet.
assert "Prev Pg" not in text, "the obsolete carry-forward row is still printed"
assert "PRIOR PG" not in text, "the obsolete carry-forward row is still printed"

pdf = fitz.open(PDF)
sizes = []
for index, page in enumerate(pdf):
    sizes.append([round(page.rect.width, 1), round(page.rect.height, 1)])
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pixmap.save(OUT / f"page-v15-{index + 1}.png")

# Page order matches sheetDefinitions: Club Dance Dollar Tips (landscape), Cage
# SmartTab Tip Totals (landscape), Chip Totals Sheet (portrait).
assert sizes[0][0] > sizes[0][1], sizes
assert sizes[1][0] > sizes[1][1], sizes
assert sizes[2][0] < sizes[2][1], sizes

# Printed labels must be upright. Walk every text line in the PDF text layer and
# refuse any line whose writing direction is not horizontal, which is exactly how
# the sideways "Total" label showed up before. The "Prev Pg" / "PRIOR PG"
# carry-forward row was removed entirely, so it must no longer appear at all.
sideways = []
labels = {"Total": 0, "TOTAL": 0}
for index, page in enumerate(pdf):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            direction = line.get("dir", (1.0, 0.0))
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if direction[0] < 0.99 or abs(direction[1]) > 0.02:
                sideways.append({"page": index + 1, "text": line_text, "dir": [round(value, 3) for value in direction]})
            for label in labels:
                if line_text.startswith(label):
                    labels[label] += 1

assert not sideways, f"sideways text in the printed sheets: {sideways}"
for label, count in labels.items():
    assert count >= 1, f"label {label!r} missing from the printed text layer"

print(json.dumps({"pages": len(reader.pages), "sizes": sizes, "titles": 4, "brand_marks": 3, "text_values_verified": len(verified_values)}, indent=2))
print(json.dumps({"upright_text_lines": True, "sideways_lines": 0, "label_lines": labels}, indent=2))
