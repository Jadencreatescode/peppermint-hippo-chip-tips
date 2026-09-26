import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification"
CHROMIUM = Path("/opt/data/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
URL = "http://127.0.0.1:8787"
SHIFT = {
    "version": 3, "id": "shot-1", "work_date": "2026-09-22", "shift": "Night", "tip_pool_day": "Tuesday",
    "workers": ["Karla", "Employee 1"], "bank_start_time": "21:30", "bank_end_time": "05:30",
    "tipRows": [{"id": "tip-1", "customer_name": "Shared Guest", "drawer_number": "3", "check_number": "256", "tip_amount": "20", "entry_type": "DD", "card_type": "Visa", "location": "Main Floor", "host": "Kaleb", "time_closed": "18:30"}],
    "chipRows": [{"id": "chip-1", "transfer_to": "04", "tab_number": "57", "chip_total_invoice": "520", "tip_smarttab": "124.80"}],
}


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(CHROMIUM), args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=1)
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate(
            "([key, shift]) => { state.shift = shift; localStorage.setItem(key, JSON.stringify(shift)); }",
            ["chip_tips_active_shift_v2", SHIFT],
        )
        await page.reload(wait_until="networkidle")
        await page.locator('header nav [data-page="master"]').click()
        await page.locator("#page-master.active").wait_for()
        await page.locator(".transaction-row").first.screenshot(path=str(OUT / "master-transaction-paired-v14.png"))
        await page.locator("header nav [data-page=\"sheets\"]").click()
        await page.locator('[data-view-sheet="chip-totals"]').click()
        await page.locator(".generated-preview-panel").screenshot(path=str(OUT / "chip-totals-preview-paired-v14.png"))
        await browser.close()


asyncio.run(main())
