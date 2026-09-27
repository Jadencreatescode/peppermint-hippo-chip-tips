"""Regression guard for the exact bug found while doubling print font sizes:
scaling every print rule up can still report a correct PDF page COUNT while
silently overflowing a page's content box, which drops a row and bleeds a
duplicate copy of the brand mark onto the next page. Page count alone did not
catch this; only rendering full 30/25-row sheets and reading the actual text
per page did. This script renders full sheets and re-checks that ground truth
directly, so any future font/size change that reintroduces the overflow fails
loudly instead of silently shipping a broken printed sheet.
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification"
OUT.mkdir(exist_ok=True)
CHROMIUM = Path("/opt/data/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
URL = "http://127.0.0.1:8787"


def make_shift(n_tip_rows=30, n_chip_rows=25):
    tip_rows = [
        {
            "id": f"t{i}", "customer_name": f"Guest {i}", "drawer_number": "3",
            "check_number": str(500 + i), "tip_amount": "20", "entry_type": "DD",
            "card_type": "Visa", "location": "Main Floor", "host": "Kaleb", "time_closed": "20:00",
        }
        for i in range(n_tip_rows)
    ]
    chip_rows = [
        {"id": f"c{i}", "transfer_to": "04", "tab_number": str(500 + i), "chip_total_invoice": "100", "tip_smarttab": "20"}
        for i in range(n_chip_rows)
    ]
    return {
        "version": 3, "id": "thirty-line-print-check", "work_date": "2026-09-27", "shift": "Night",
        "tip_pool_day": "Sunday", "workers": ["Karla"], "bank_start_time": "21:00", "bank_end_time": "05:00",
        "tipRows": tip_rows, "chipRows": chip_rows,
    }


async def main():
    shift = make_shift()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, executable_path=str(CHROMIUM), args=["--no-sandbox"])
        page = await browser.new_page()
        await page.add_init_script(
            f"localStorage.setItem('chip_tips_active_shift_v2', {json.dumps(json.dumps(shift))});"
        )
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate(
            """(shift) => {
                document.querySelector('#printReport').innerHTML = sheetDefinitions
                  .map(item => `<section class="print-sheet ${item.id}">${generatedSheetHtml(item.id, true, shift)}</section>`)
                  .join('');
            }""",
            shift,
        )
        await page.emulate_media(media="print")
        pdf_bytes = await page.pdf(print_background=True, prefer_css_page_size=True)
        await browser.close()

    import pymupdf as fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) == 3, f"expected exactly 3 pages for 30/25-row sheets, got {len(doc)} (a page overflowed)"

    expected_sizes = [(11.0, 8.5), (11.0, 8.5), (8.5, 11.0)]
    for index, page_obj in enumerate(doc):
        size = (round(page_obj.rect.width / 72, 1), round(page_obj.rect.height / 72, 1))
        assert size == expected_sizes[index], f"page {index} is {size}, expected {expected_sizes[index]}"
        text = page_obj.get_text()
        brand_count = text.count("PEPPERMINT HIPPO")
        assert brand_count == 1, (
            f"page {index} has {brand_count} copies of the brand mark, expected exactly 1 — "
            "a duplicate means content overflowed the page and bled onto the next one"
        )

    club_text = doc[0].get_text()
    cage_text = doc[1].get_text()
    # The last populated data row and the row-30 number label must both reach
    # the page: if content overflowed, either the row itself gets cut off the
    # bottom of the page, or the trailing blank row numbers (26-30) go missing
    # because the table never finishes rendering within the page box.
    assert "Guest 24" in club_text, "the last populated row is missing from the Club Dance Dollar Tips print — page overflowed"
    assert "Guest 24" in cage_text, "the last populated row is missing from the Cage SmartTab print — page overflowed"
    for label in ("26", "27", "28", "29", "30"):
        assert f"\n{label}\n" in club_text, f"row number {label} missing from Club Dance Dollar Tips — page overflowed"
        assert f"\n{label}\n" in cage_text, f"row number {label} missing from Cage SmartTab — page overflowed"

    chip_text = doc[2].get_text()
    assert "524" in chip_text, "row 25 (tab 524) missing from the Chip Totals print — page overflowed"
    for label in ("21", "22", "23", "24", "25"):
        assert f"\n{label}\n" in chip_text, f"row number {label} missing from Chip Totals — page overflowed"

    for index, page_obj in enumerate(doc):
        pixmap = page_obj.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(OUT / f"thirty-line-print-page-{index + 1}.png")

    print(json.dumps({"pages": len(doc), "sizes": expected_sizes, "brand_marks_per_page": 1, "all_rows_present": True}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
