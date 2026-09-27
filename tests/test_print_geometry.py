"""Print geometry checks for the three worksheets.

The operator requirement this enforces: the text printed inside the sheet boxes
must be upright (never rotated) and centred inside its box, and nothing may be
clipped. It runs in the real layout engine under print media, because that is
what the printer actually renders.

Run with the local preview server up:
    python3 server.py &
    uv run --with playwright python tests/test_print_geometry.py
"""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

from test_browser import SHIFT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification"
OUT.mkdir(exist_ok=True)
# Override to run the same geometry check against the published preview.
URL = os.environ.get("CHIP_TIPS_URL", "http://127.0.0.1:8787")

CANDIDATES = [
    Path("/opt/data/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
    Path("/usr/bin/google-chrome"),
]
CHROMIUM = next((path for path in CANDIDATES if path.exists()), None)

# Labels the operator circled as printing sideways. Each must be upright and
# centred on both axes inside its cell. The "Prev Pg" / "PRIOR PG" carry-forward
# row was removed (the app now prints every page of a multi-page shift at once,
# so there is nothing to carry forward), so only the Total labels remain.
LABELS = ["Total", "TOTAL"]

# Sub pixel slack for "centred". Horizontal: a 22 pixel tall, 40 pixel wide cell
# with 1.5 pixels of horizontal imbalance is visibly off centre, so this bound is
# meaningful (the last measurements were 0.02px). Vertical: the browser centres
# the line box, which leaves an even residual of about 0.7px per side in every
# cell because of font ascent and descent rounding, so the bounds differ. A label
# that is actually top aligned is off by 7px or more, so 2.0px still catches it.
TOLERANCE_X = 1.5
TOLERANCE_Y = 2.0

MEASURE_JS = """
() => {
  const round = value => Math.round(value * 100) / 100;
  const records = [];
  const sheets = document.querySelectorAll('#printReport .print-sheet');
  for (const sheet of sheets) {
    for (const table of sheet.querySelectorAll('.paper-table')) {
      for (const cell of table.querySelectorAll('th, td')) {
        const style = getComputedStyle(cell);
        const box = cell.getBoundingClientRect();
        if (box.width === 0 || box.height === 0) continue;
        const contentLeft = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
        const contentRight = box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
        const contentTop = box.top + parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop);
        const contentBottom = box.bottom - parseFloat(style.borderBottomWidth) - parseFloat(style.paddingBottom);
        const range = document.createRange();
        range.selectNodeContents(cell);
        const text = range.getBoundingClientRect();
        const empty = cell.textContent.trim() === '' || text.width === 0;
        const record = {
          sheet: sheet.className.split(' ').pop(),
          label: cell.textContent.trim().slice(0, 24),
          writingMode: style.writingMode,
          transform: style.transform,
          textAlign: style.textAlign,
          verticalAlign: style.verticalAlign,
          empty: empty,
          cellWidth: round(box.width),
          cellHeight: round(box.height),
        };
        if (!empty) {
          record.leftGap = round(text.left - contentLeft);
          record.rightGap = round(contentRight - text.right);
          record.topGap = round(text.top - contentTop);
          record.bottomGap = round(contentBottom - text.bottom);
          record.offsetX = round(Math.abs(record.leftGap - record.rightGap));
          record.offsetY = round(Math.abs(record.topGap - record.bottomGap));
          record.clipX = record.leftGap < -0.5 || record.rightGap < -0.5;
          record.clipY = record.topGap < -0.5 || record.bottomGap < -0.5;
        } else {
          record.clipX = cell.scrollWidth > cell.clientWidth + 1;
          record.clipY = cell.scrollHeight > cell.clientHeight + 1;
        }
        records.push(record);
      }
    }
  }
  return records;
}
"""


async def main():
    assert CHROMIUM, "no chromium executable found for the print geometry check"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(CHROMIUM), args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 412, "height": 915}, device_scale_factor=1)
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate(
            "([key, shift, archiveKey]) => { state.shift = shift; state.archives = []; localStorage.setItem(key, JSON.stringify(shift)); localStorage.removeItem(archiveKey); }",
            ["chip_tips_active_shift_v2", SHIFT, "chip_tips_completed_shifts_v1"],
        )
        await page.reload(wait_until="networkidle")
        await page.evaluate(
            """
            () => {
                const source = state.shift;
                document.querySelector('#printReport').innerHTML = sheetDefinitions
                  .map(item => `<section class="print-sheet ${item.id}">${generatedSheetHtml(item.id, true, source)}</section>`)
                  .join('');
            }
            """
        )
        await page.emulate_media(media="print")
        # A printed sheet is laid out at its page content box width, not at phone
        # width: letter portrait with 0.3in margins is 7.9in, landscape 10.4in.
        records = []
        for sheet_id, page_width in [("chip-tips", 998), ("cage", 998), ("chip-totals", 758)]:
            await page.set_viewport_size({"width": page_width, "height": 1200})
            await page.wait_for_timeout(60)
            measured = await page.evaluate(MEASURE_JS)
            records.extend([row for row in measured if row["sheet"] == sheet_id])
            await page.locator(f"#printReport .print-sheet.{sheet_id}").screenshot(path=str(OUT / f"print-{sheet_id}-{page_width}px-v21.png"))
        await page.emulate_media(media="screen")
        await browser.close()

    failures = []
    labelled = {}
    cells_with_text = 0
    cells_centred = 0
    worst = {"offsetX": 0.0, "offsetY": 0.0}
    per_sheet = {}
    for record in records:
        where = f"{record['sheet']} / '{record['label']}'"
        if record["writingMode"] != "horizontal-tb":
            failures.append(f"{where} writing-mode is {record['writingMode']}, text is not upright")
        if record["transform"] not in ("none", "matrix(1, 0, 0, 1, 0, 0)"):
            failures.append(f"{where} transform is {record['transform']}, text may be rotated")
        if record["clipX"] or record["clipY"]:
            failures.append(f"{where} content is clipped (clipX={record['clipX']}, clipY={record['clipY']})")
        if record["empty"]:
            continue
        cells_with_text += 1
        bucket = per_sheet.setdefault(record["sheet"], {"cells": 0, "offCentre": 0, "worstOffsetX": 0.0})
        bucket["cells"] += 1
        if record["label"] in LABELS:
            labelled.setdefault(record["label"], []).append(record)
        worst["offsetX"] = max(worst["offsetX"], record["offsetX"])
        worst["offsetY"] = max(worst["offsetY"], record["offsetY"])
        bucket["worstOffsetX"] = max(bucket["worstOffsetX"], record["offsetX"])
        # Every printed box holds its content in the middle of the box, so a value
        # never sits against the left or right edge of its column.
        offset_x = record["offsetX"] > TOLERANCE_X
        offset_y = record["offsetY"] > TOLERANCE_Y
        if offset_x:
            failures.append(
                f"{where} is off centre horizontally by {record['offsetX']}px "
                f"(left {record['leftGap']}, right {record['rightGap']}, align {record['textAlign']})"
            )
        if offset_y:
            failures.append(
                f"{where} is off centre vertically by {record['offsetY']}px "
                f"(top {record['topGap']}, bottom {record['bottomGap']})"
            )
        if offset_x or offset_y:
            bucket["offCentre"] += 1
        else:
            cells_centred += 1

    missing = [label for label in LABELS if label not in labelled]
    if missing:
        failures.append(f"label cells not found in the printed sheets: {missing}")

    if failures:
        raise AssertionError("print geometry failures:\n" + "\n".join(failures))

    print(json.dumps({
        "cells_measured": len(records),
        "cells_with_text": cells_with_text,
        "cells_centred": cells_centred,
        "off_centre_cells": cells_with_text - cells_centred,
        "worst_offsets_px": {key: round(value, 2) for key, value in worst.items()},
        "per_sheet": per_sheet,
        "labels_checked": {label: len(rows) for label, rows in sorted(labelled.items())},
        "labels_centred": {
            label: [
                {"sheet": row["sheet"], "offsetX": row["offsetX"], "offsetY": row["offsetY"], "cell": [row["cellWidth"], row["cellHeight"]]}
                for row in rows
            ]
            for label, rows in sorted(labelled.items())
        },
        "clipped_cells": 0,
        "tolerance_px": {"horizontal": TOLERANCE_X, "vertical": TOLERANCE_Y},
        "screenshots": [
            str(OUT / "print-chip-tips-998px-v21.png"),
            str(OUT / "print-cage-998px-v21.png"),
            str(OUT / "print-chip-totals-758px-v21.png"),
        ],
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
