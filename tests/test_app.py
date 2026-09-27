import json
import re
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

import server

try:  # the suite runs both as "tests.test_app" and as a discovered top level module
    from tests.png_probe import read_png
except ModuleNotFoundError:  # pragma: no cover - import shape depends on how the suite is launched
    from png_probe import read_png

ROOT = Path(__file__).resolve().parents[1]


class ChipTipsMasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def fetch(self, path):
        with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as response:
            return response.status, response.headers, response.read()

    def test_all_runtime_assets_are_served(self):
        for path in ["/", "/styles.css", "/logic.js", "/app.js", "/manifest.webmanifest", "/sw.js", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/icon-maskable-192.png", "/icons/icon-maskable-512.png", "/icons/apple-touch-icon-180.png", "/brand/peppermint-hippo-mark.png", "/brand/peppermint-hippo-logo.png"]:
            status, _, body = self.fetch(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body, path)

    def test_three_generated_sheets_and_master_entry_exist(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        for text in ["Master Shift", "Shared tips", "Chip totals", "Print all three sheets"]:
            self.assertIn(text, html)
        for sheet_id in ["chip-tips", "cage", "chip-totals"]:
            self.assertIn(f'id:"{sheet_id}"', app)
        self.assertIn("generatedSheetHtml", app)

    def test_master_data_is_local_only(self):
        app = (ROOT / "static" / "app.js").read_text()
        server_source = (ROOT / "server.py").read_text()
        self.assertIn("localStorage.setItem(SHIFT_KEY", app)
        self.assertNotIn("/api/", app)
        self.assertNotRegex(app, r"\bfetch\s*\(")
        self.assertNotIn("sqlite", server_source.lower())
        self.assertNotIn("do_POST", server_source)

    def test_no_horizontal_form_scrolling_layout(self):
        css = (ROOT / "static" / "styles.css").read_text()
        self.assertIn("overflow-x:hidden", css)
        self.assertIn("@media(max-width:540px)", css)
        self.assertIn(".transaction-row{grid-template-columns:1fr 1fr}", css)
        self.assertNotIn("min-width:1330px", css)
        html = (ROOT / "static" / "index.html").read_text()
        self.assertNotIn("table-scroll", html)

    def test_completion_archives_shift_and_new_shift_is_separate(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        for element_id in ["completedShiftList", "completeShiftButton", "savePdfButton", "startNewShiftButton"]:
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('const ARCHIVE_KEY = "chip_tips_completed_shifts_v1"', app)
        self.assertIn("upsertCompletedShift", app)
        self.assertIn("localStorage.setItem(ARCHIVE_KEY", app)
        self.assertIn("function openCompletedShift", app)
        self.assertIn("function startNewShift", app)
        self.assertIn("renderPrint(sheetDefinitions.map", app)
        self.assertNotIn("Download emergency copy", html)
        self.assertNotIn("Clear shift", html)
        self.assertNotIn("function exportShift", app)
        self.assertIn("@media print", (ROOT / "static" / "styles.css").read_text())

    def test_every_direct_remove_action_has_a_confirmation_gate(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        self.assertIn('id="removeDialog"', html)
        self.assertIn('id="confirmRemoveButton"', html)
        self.assertIn("requestRemoval(\"transaction\"", app)
        self.assertIn("requestRemoval(\"option\"", app)
        self.assertNotIn('class="remove-row" aria-label=', app)

    def test_final_invoice_includes_fee_room_and_tip(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        self.assertIn("Final invoice equals chip invoice", html)
        self.assertIn("finalInvoice = grandInvoice + tipSmartTab", logic)
        self.assertIn('data-result="totalWithTip"', app)
        self.assertIn('$("#finalInvoiceTotal")', app)

    def test_completed_sheet_uses_one_before_tip_value(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        self.assertIn("Check total without tip is filled automatically", html)
        self.assertNotIn('data-field="check_total_without_tip"', app)
        self.assertIn("const checkWithoutTip = grandInvoice", logic)

    def test_entry_screen_has_one_transaction_questionnaire(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        self.assertIn('id="transactionRows"', html)
        self.assertNotIn('class="entry-tabs"', html)
        self.assertNotIn('data-entry-panel=', html)
        self.assertNotIn('id="tipRows"', html)
        self.assertNotIn('id="chipRows"', html)
        self.assertIn("function renderTransactionRows", app)
        self.assertIn("function addTransaction", app)
        self.assertIn("function alignTransactionRows", app)
        self.assertIn("transactions</p>", app)
        self.assertNotIn("customer lines", app)
        self.assertNotIn("chip lines", app)

    def test_one_transaction_contains_every_input_for_all_three_sheets(self):
        app = (ROOT / "static" / "app.js").read_text()
        match = re.search(r"function renderTransactionRows\(\)\{(.+?)\nfunction updateAllTotals", app, re.S)
        self.assertIsNotNone(match)
        entry = match.group(1)
        fields = [
            "customer_name", "drawer_number", "check_number", "tip_amount", "entry_type",
            "card_type", "location", "host", "time_closed", "transfer_to",
            "chip_total_invoice",
        ]
        for field in fields:
            self.assertEqual(entry.count(f'data-field="{field}"'), 1)
        self.assertEqual(entry.count('data-field="'), len(fields))
        self.assertEqual(entry.count('data-field="tab_number"'), 0)
        self.assertEqual(entry.count('data-field="tip_smarttab"'), 0)
        self.assertNotIn('data-field="room_fee_invoice"', entry)
        self.assertIn('data-result="grandInvoice"', entry)
        self.assertIn('data-result="totalWithTip"', entry)

    def test_check_number_and_tab_number_are_asked_for_once(self):
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        self.assertIn('field("Check # / Tab #"', app)
        self.assertIn('field("Customer tip / SmartTab tip"', app)
        self.assertIn("Logic.pairedChipFields(tip,chip)", app)
        self.assertIn("Logic.pairShiftFields(state.shift.tipRows,state.shift.chipRows)", app)
        self.assertIn("Logic.pairShiftFields(snapshot.tipRows,snapshot.chipRows)", app)
        self.assertIn("Logic.pairShiftFields(state.viewingShift.tipRows,state.viewingShift.chipRows)", app)
        self.assertIn("chip.tab_number = checkNumber", logic)
        self.assertIn("chip.tip_smarttab = customerTip", logic)
        self.assertIn("check_number: checkNumber", logic)

    def test_room_fee_is_not_part_of_the_questionnaire(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        self.assertNotIn("Room fee", html)
        self.assertNotIn('data-field="room_fee_invoice"', app)

    def test_transfer_to_routing_is_explained(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        self.assertIn("Any numeric Transfer To value beginning with zero is shared", html)
        self.assertIn("Normal Transfer To numbers stay on Cage SmartTab and Chip Totals", html)
        self.assertIn('placeholder="0406 for shared"', app)
        self.assertIn("Shared tip", app)
        self.assertIn("Separate tip", app)
        self.assertIn("calculateSharedTipTotals", app)
        self.assertIn("printableSharedTipRows", app)

    def test_completed_chip_totals_print_columns_match_reference(self):
        app = (ROOT / "static" / "app.js").read_text()
        expected_header = (
            '<span>Xfer to</span><span>#</span><span>Tab #</span>'
            '<span>Chip Total Invoice</span><span>Chip Total + Chip Fee</span>'
            '<span>Room Fee Invoice</span><span>Grand Total Invoice</span>'
            '<span>Check Total Without Tip</span><span>Tip SmartTab</span>'
            '<span>Total With Tip SmartTab</span>'
        )
        self.assertIn(expected_header, app)
        css = (ROOT / "static" / "styles.css").read_text()
        self.assertIn(
            ".chip-total-table .read-row{grid-template-columns:.62fr .3fr .58fr .68fr .64fr .62fr .68fr .78fr .56fr .72fr!important}",
            css,
        )

    def test_generated_sheets_match_uploaded_paper_forms(self):
        app = (ROOT / "static" / "app.js").read_text()
        css = (ROOT / "static" / "styles.css").read_text()
        for title in ["CLUB DANCE DOLLAR TIPS", "SUPERVISOR TAB TOTALS", "CAGE SMARTTAB TIP TOTALS", "CHIP TOTALS SHEET"]:
            self.assertIn(title, app)
        for class_name in ["club-tips-form", "cage-smarttab-form", "chip-totals-form", "paper-field", "paper-total-row", "paper-prev-row"]:
            self.assertIn(class_name, app)
        self.assertIn("paperRows(25", app)
        self.assertIn("paperRows(30", app)
        self.assertIn("@page portrait-sheet", css)
        self.assertIn("@page landscape-sheet", css)
        self.assertIn("page:portrait-sheet", css)
        self.assertIn("page:landscape-sheet", css)
        self.assertIn("print-color-adjust:exact", css)

    def test_peppermint_hippo_branding_matches_contractor_app(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        css = (ROOT / "static" / "styles.css").read_text()
        manifest = json.loads((ROOT / "static" / "manifest.webmanifest").read_text())
        self.assertIn('src="brand/peppermint-hippo-mark.png"', html)
        self.assertIn("Peppermint Hippo", html)
        self.assertIn("Chip Tips · Las Vegas", html)
        self.assertIn("paper-brand", app)
        self.assertIn("PEPPERMINT HIPPO", app)
        self.assertIn("LAS VEGAS", app)
        self.assertIn("--brand:#d5000c", css)
        self.assertIn("--brand-strong:#a90009", css)
        self.assertIn("--canvas:#f3eee8", css)
        self.assertEqual(manifest["name"], "Peppermint Hippo Chip Tips")
        self.assertEqual(manifest["theme_color"], "#191516")

    def test_cage_app_icon_is_built_from_the_uploaded_sign(self):
        icons = {
            "static/icons/icon-192.png": 192,
            "static/icons/icon-512.png": 512,
            "static/icons/icon-maskable-192.png": 192,
            "static/icons/icon-maskable-512.png": 512,
            "static/icons/apple-touch-icon-180.png": 180,
        }
        for relative, size in icons.items():
            image = read_png(ROOT / relative)
            self.assertEqual((image.width, image.height), (size, size), relative)
            self.assertGreater(image.mean_luminance(), 195, relative)
            self.assertTrue(0.03 < image.dark_ratio() < 0.45, relative)
            left, top, right, bottom = image.content_box()
            aspect = (right - left + 1) / (bottom - top + 1)
            self.assertTrue(2.0 < aspect < 2.6, f"{relative} wordmark aspect {aspect:.3f}")
        # the wide four letter wordmark must stay four separate letters at full size
        for relative in ["static/icons/icon-512.png", "static/icons/icon-maskable-512.png"]:
            self.assertEqual(read_png(ROOT / relative).content_column_groups(), 4, relative)
        # Android only guarantees the centre circle of a maskable icon survives masking
        for relative in ["static/icons/icon-maskable-192.png", "static/icons/icon-maskable-512.png"]:
            self.assertLessEqual(read_png(ROOT / relative).content_half_diagonal(), 0.40, relative)
        # iOS composites onto black, so the touch icon must carry no transparency
        self.assertEqual(read_png(ROOT / "static/icons/apple-touch-icon-180.png").min_alpha(), 255)
        html = (ROOT / "static" / "index.html").read_text()
        self.assertIn('rel="apple-touch-icon" href="icons/apple-touch-icon-180.png"', html)
        manifest = json.loads((ROOT / "static" / "manifest.webmanifest").read_text())
        purposes = [icon["purpose"] for icon in manifest["icons"]]
        self.assertEqual(purposes, ["any", "any", "maskable", "maskable"])
        sources = [icon["src"] for icon in manifest["icons"]]
        self.assertEqual(sources, ["icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-192.png", "icons/icon-maskable-512.png"])
        # the uploaded sign stays in the project so the icons can be rebuilt
        self.assertTrue((ROOT / "assets" / "brand" / "cage-sign-source.jpeg").exists())
        self.assertTrue((ROOT / "scripts" / "build_icons.py").exists())

    def test_print_labels_are_upright_and_centred(self):
        css = (ROOT / "static" / "styles.css").read_text()
        # Sheet labels were rotated 90 degrees once and printed sideways; the
        # printer must always receive upright, centred text.
        self.assertNotIn("writing-mode:vertical", css)
        self.assertNotIn("rotate(180deg)", css)
        match = re.search(r"\.paper-prev-row th:first-child,\.paper-total-row th:first-child\{([^}]*)\}", css)
        self.assertIsNotNone(match, "the label cell rule is missing from the print stylesheet")
        declarations = match.group(1)
        for declaration in ["writing-mode:horizontal-tb", "text-align:center", "vertical-align:middle", "white-space:nowrap"]:
            self.assertIn(declaration, declarations)
        for forbidden in ["writing-mode:vertical", "rotate(", "text-align:left"]:
            self.assertNotIn(forbidden, declarations)

    def test_print_values_are_centred_in_their_columns(self):
        css = (ROOT / "static" / "styles.css").read_text()
        # Values once sat against the left edge of the wide club and cage columns
        # while the chip totals form was centred. Every printed box now holds its
        # content in the middle of the box.
        match = re.search(r"\.paper-table th,\.paper-table td\{([^}]*)\}", css)
        self.assertIsNotNone(match, "the shared paper table rule is missing from the print stylesheet")
        declarations = match.group(1)
        self.assertIn("text-align:center", declarations)
        self.assertIn("vertical-align:middle", declarations)
        self.assertNotIn("text-align:left", declarations)

    def test_dom_references_resolve(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        ids = set(re.findall(r'id="([^"]+)"', html))
        refs = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"', app))
        self.assertEqual(sorted(refs - ids), [])

    def test_manifest_and_offline_shell(self):
        manifest = json.loads((ROOT / "static" / "manifest.webmanifest").read_text())
        self.assertEqual(manifest["display"], "standalone")
        sw = (ROOT / "static" / "sw.js").read_text()
        self.assertIn('const CACHE = "chip-tips-master-v15"', sw)
        for asset in ["./", "styles.css?v=15", "logic.js?v=15", "app.js?v=15", "manifest.webmanifest?v=15", "brand/peppermint-hippo-mark.png", "brand/peppermint-hippo-logo.png", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-192.png", "icons/icon-maskable-512.png"]:
            self.assertIn(f'"{asset}"', sw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
