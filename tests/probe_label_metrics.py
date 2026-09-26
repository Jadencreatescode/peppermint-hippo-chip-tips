import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

CHROMIUM = "/opt/data/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
URL = "http://127.0.0.1:8787"

PROBE = """
() => {
  const out = [];
  for (const sheet of document.querySelectorAll('#printReport .print-sheet')) {
    const sheetId = sheet.className.split(' ').pop();
    for (const table of sheet.querySelectorAll('.paper-table')) {
      const rows = [...table.querySelectorAll('tr')];
      const last = rows[rows.length - 1];
      const prev = rows[rows.length - 2];
      for (const row of [prev, last]) {
        if (!row) continue;
        for (const [index, cell] of [...row.children].entries()) {
          const style = getComputedStyle(cell);
          const box = cell.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(cell);
          const text = range.getBoundingClientRect();
          out.push({
            sheet: sheetId, row: row.className || 'tfoot-row', index,
            text: cell.textContent.trim().slice(0, 18),
            cellRect: [Math.round(box.top * 100) / 100, Math.round(box.height * 100) / 100],
            textHeight: Math.round(text.height * 100) / 100,
            textTopOffset: Math.round((text.top - box.top) * 100) / 100,
            textBottomOffset: Math.round((box.bottom - text.bottom) * 100) / 100,
            fontSize: style.fontSize, lineHeight: style.lineHeight,
            border: [style.borderTopWidth, style.borderBottomWidth],
            padding: [style.paddingTop, style.paddingBottom],
            verticalAlign: style.verticalAlign,
            cellsInRow: row.children.length,
            rowHeight: Math.round(row.getBoundingClientRect().height * 100) / 100,
          });
        }
      }
    }
  }
  return out;
}
"""


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=CHROMIUM, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 998, "height": 1200})
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate(
            "([key, shift]) => { state.shift = JSON.parse(shift); localStorage.setItem(key, shift); }",
            ["chip_tips_active_shift_v2", '{"version":3,"id":"probe","work_date":"2026-09-22","shift":"Night","tip_pool_day":"Tuesday","workers":["Karla"],"bank_start_time":"21:30","bank_end_time":"05:30","tipRows":[{"id":"t1","customer_name":"Shared Guest","drawer_number":"3","check_number":"256","tip_amount":"20","entry_type":"DD","card_type":"Visa","location":"Main Floor","host":"Kaleb","time_closed":"18:30"}],"chipRows":[{"id":"c1","transfer_to":"04","tab_number":"57","chip_total_invoice":"520","tip_smarttab":"124.80"}]}'],
        )
        await page.reload(wait_until="networkidle")
        await page.evaluate(
            """
            () => {
                document.querySelector('#printReport').innerHTML = sheetDefinitions
                  .map(item => `<section class="print-sheet ${item.id}">${generatedSheetHtml(item.id, true, state.shift)}</section>`)
                  .join('');
            }
            """
        )
        await page.emulate_media(media="print")
        for sheet_id, width in [("chip-tips", 998), ("cage", 758), ("chip-totals", 758)]:
            await page.set_viewport_size({"width": width, "height": 1200})
            await page.wait_for_timeout(60)
            for record in await page.evaluate(PROBE):
                if record["sheet"] != sheet_id:
                    continue
                print(f"{record['sheet']:12} row={record['row']:10} col{record['index']} '{record['text']:18}' "
                      f"cellTop={record['cellRect'][0]} cellH={record['cellRect'][1]} rowH={record['rowHeight']} "
                      f"textH={record['textHeight']} topOff={record['textTopOffset']} botOff={record['textBottomOffset']} "
                      f"font={record['fontSize']}/{record['lineHeight']} pad={record['padding']} valign={record['verticalAlign']}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
