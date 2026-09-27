import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification"
OUT.mkdir(exist_ok=True)
CHROMIUM = Path("/opt/data/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
URL = "http://127.0.0.1:8787"

SHIFT = {
    "version": 3,
    "id": "browser-shift-1",
    "work_date": "2026-09-22",
    "shift": "Night",
    "tip_pool_day": "Tuesday",
    "workers": ["Karla", "Employee 1"],
    "bank_start_time": "21:30",
    "bank_end_time": "05:30",
    "tipRows": [
        {
            "id": "tip-1",
            "customer_name": "Shared Guest",
            "drawer_number": "3",
            "check_number": "256",
            "tip_amount": "20",
            "entry_type": "DD",
            "card_type": "Visa",
            "location": "Main Floor",
            "host": "Kaleb",
            "time_closed": "18:30",
        },
        {
            "id": "tip-2",
            "customer_name": "Window Guest",
            "drawer_number": "4",
            "check_number": "257",
            "tip_amount": "10",
            "entry_type": "C",
            "card_type": "Mastercard",
            "location": "VIP Room",
            "host": "Host 1",
            "time_closed": "18:45",
        },
    ],
    "chipRows": [
        {
            "id": "chip-1",
            "transfer_to": "04",
            "tab_number": "57",
            "chip_total_invoice": "520",
            "tip_smarttab": "124.80",
        },
        {
            "id": "chip-2",
            "transfer_to": "406",
            "tab_number": "81",
            "chip_total_invoice": "1520",
            "tip_smarttab": "364.80",
        },
    ],
}


async def main():
    console_errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=str(CHROMIUM),
            args=["--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": 412, "height": 915}, device_scale_factor=1)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate(
            "([key, shift, archiveKey]) => { state.shift = shift; state.archives = []; localStorage.setItem(key, JSON.stringify(shift)); localStorage.removeItem(archiveKey); }",
            ["chip_tips_active_shift_v2", SHIFT, "chip_tips_completed_shifts_v1"],
        )
        await page.reload(wait_until="networkidle")

        assert await page.locator('script[src="app.js?v=17"]').count() == 1
        assert await page.evaluate("document.querySelector('link[rel=\"apple-touch-icon\"]').getAttribute('href')") == "icons/apple-touch-icon-180.png"
        icon = await page.evaluate(
            """(async () => {
                const response = await fetch('icons/icon-maskable-512.png');
                const bitmap = await createImageBitmap(await response.blob());
                return [response.status, bitmap.width, bitmap.height];
            })()"""
        )
        assert icon == [200, 512, 512], icon
        assert await page.locator('.brand img[src="brand/peppermint-hippo-mark.png"]').is_visible()
        assert await page.get_by_text("Peppermint Hippo", exact=True).is_visible()
        assert await page.get_by_text("Chip Tips · Las Vegas", exact=True).is_visible()
        assert await page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        # The check number and the tab number are one value, and the customer tip and the
        # SmartTab tip are one value, so the questionnaire asks for each pair once.
        await page.locator('header nav [data-page="master"]').click()
        await page.locator("#page-master.active").wait_for()
        assert await page.locator('[data-field="tab_number"], [data-field="tip_smarttab"]').count() == 0
        assert await page.get_by_text("Check # / Tab #", exact=True).count() >= 1
        assert await page.get_by_text("Customer/SmartTab tip", exact=True).count() >= 1
        assert await page.locator("input[data-field=\"check_number\"][inputmode=\"numeric\"]").count() == 2
        assert await page.locator("input[data-field=\"tip_amount\"][type=\"number\"]").count() == 2
        await page.locator('[data-field="check_number"]').first.fill("999")
        await page.locator('[data-field="tip_amount"]').first.fill("42.5")
        paired = await page.evaluate("state.shift.chipRows[0].tab_number + '|' + state.shift.chipRows[0].tip_smarttab")
        # tip_amount is rounded to a whole dollar on input, so 42.5 becomes 43
        assert paired == "999|43", paired
        await page.evaluate(
            "([shift, key]) => { state.shift = shift; localStorage.setItem(key, JSON.stringify(shift)); }",
            [SHIFT, "chip_tips_active_shift_v2"],
        )
        await page.reload(wait_until="networkidle")
        assert await page.evaluate("state.shift.chipRows[0].tab_number + '|' + state.shift.chipRows[0].tip_smarttab") == "256|20"

        await page.locator('header nav [data-page="sheets"]').click()
        await page.locator('[data-view-sheet="chip-tips"]').click()
        assert await page.get_by_text("CLUB DANCE DOLLAR TIPS", exact=True).count() == 1
        assert await page.get_by_text("SUPERVISOR TAB TOTALS", exact=True).count() == 1
        await page.locator('[data-view-sheet="cage"]').click()
        assert await page.get_by_text("CAGE SMARTTAB TIP TOTALS", exact=True).count() == 1
        await page.locator('[data-view-sheet="chip-totals"]').click()
        assert await page.get_by_text("CHIP TOTALS SHEET", exact=True).count() == 1

        await page.evaluate("state.shift.shift = ''; saveLocal(false)")
        await page.locator('header nav [data-page="close"]').click()
        assert await page.locator("#completeShiftButton").is_enabled()
        await page.get_by_text("The shift can still be saved.", exact=True).wait_for()
        await page.evaluate("state.shift.shift = 'Night'; saveLocal(false); renderClose()")
        assert await page.locator("#completeShiftButton").is_enabled()
        assert await page.locator("#savePdfButton").is_enabled()
        await page.locator("#completeShiftButton").click()
        await page.get_by_text("Saved in Completed Shifts", exact=True).wait_for()
        archive = await page.evaluate("JSON.parse(localStorage.getItem('chip_tips_completed_shifts_v1'))")
        active = await page.evaluate("JSON.parse(localStorage.getItem('chip_tips_active_shift_v2'))")
        assert len(archive) == 1
        assert archive[0]["shift"]["tipRows"][0]["customer_name"] == "Shared Guest", archive
        assert active["tipRows"][0]["customer_name"] == "Shared Guest"
        assert await page.locator("#startNewShiftButton").is_enabled()

        await page.locator('header nav [data-page="home"]').click()
        assert await page.locator(".completed-shift-card").count() == 1
        await page.locator("#toast:not(.show)").wait_for(state="attached")
        await page.screenshot(path=str(OUT / "completed-shift-mobile-v17.png"), full_page=True)
        await page.locator(".completed-shift-card [data-open-completed]").click()
        await page.get_by_text("Viewing completed shift", exact=True).wait_for()
        assert await page.locator(".club-tips-form").count() == 1

        await page.evaluate(
            """() => {
                const source = state.viewingShift;
                document.querySelector('#printReport').innerHTML = sheetDefinitions
                  .map(item => `<section class="print-sheet ${item.id}">${generatedSheetHtml(item.id, true, source)}</section>`)
                  .join('');
            }"""
        )
        assert await page.locator("#printReport .paper-brand").count() == 3
        chip_rows = await page.evaluate(
            """() => [...document.querySelectorAll('#printReport .print-sheet.chip-totals tbody tr')]
                .map(tr => [...tr.children].map(cell => cell.textContent.trim()))"""
        )
        assert len(chip_rows) >= 2, chip_rows
        assert "256" in chip_rows[0], chip_rows[0]
        assert "$20.00" in chip_rows[0], chip_rows[0]
        assert not any("124.80" in cell for cell in chip_rows[0]), chip_rows[0]
        assert "257" in chip_rows[1], chip_rows[1]
        assert "$10.00" in chip_rows[1], chip_rows[1]
        assert not any("364.80" in cell for cell in chip_rows[1]), chip_rows[1]
        await page.emulate_media(media="print")
        await page.pdf(
            path=str(OUT / "chip-tips-v17-sample.pdf"),
            print_background=True,
            prefer_css_page_size=True,
        )
        await page.emulate_media(media="screen")
        await page.locator('header nav [data-page="close"]').click()
        page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        await page.locator("#startNewShiftButton").click()
        await page.locator("#page-master.active").wait_for()
        after_start_archives = await page.evaluate("JSON.parse(localStorage.getItem('chip_tips_completed_shifts_v1'))")
        after_start_active = await page.evaluate("JSON.parse(localStorage.getItem('chip_tips_active_shift_v2'))")
        assert len(after_start_archives) == 1
        assert after_start_archives[0]["shift"]["tipRows"][0]["customer_name"] == "Shared Guest"
        assert all(not row.get("customer_name") for row in after_start_active["tipRows"])
        assert after_start_active["id"] != "browser-shift-1"
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.locator('header nav [data-page="home"]').click()
        assert await page.locator(".brand .brand-copy").is_visible()
        assert await page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        await page.locator("#toast:not(.show)").wait_for(state="attached")
        await page.screenshot(path=str(OUT / "home-desktop-v17.png"), full_page=True)
        await browser.close()

    if console_errors:
        raise AssertionError(f"Browser console errors: {console_errors}")
    print(json.dumps({
        "archive_count": 1,
        "active_shift_preserved": True,
        "completed_shift_reopened": True,
        "new_shift_kept_archive": True,
        "pdf": str(OUT / "chip-tips-v17-sample.pdf"),
        "screenshot": str(OUT / "completed-shift-mobile-v17.png"),
        "desktop_screenshot": str(OUT / "home-desktop-v17.png"),
        "console_errors": 0,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
