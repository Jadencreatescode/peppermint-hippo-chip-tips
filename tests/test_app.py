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

    def test_chip_invoice_field_is_a_chip_count_not_a_dollar_amount(self):
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        # The field used to say "Chip invoice" and accept cents. It is a count of
        # physical $20 / $100 chips, so it must say so and step by whole chips.
        self.assertNotIn('field("Chip invoice"', app)
        self.assertIn('field("Total chips ($20s / $100s)"', app)
        self.assertIn('data-field="chip_total_invoice" value="${esc(chip.chip_total_invoice)}" type="number" min="0" step="20" inputmode="numeric"', app)
        self.assertIn("function chipAmountMatchesDenominations", logic)
        self.assertIn('data-result="chipDenomHint"', app)
        self.assertIn("chip-denom-warning", app)

    def test_cashier_number_field_is_relabeled_from_drawer(self):
        app = (ROOT / "static" / "app.js").read_text()
        # The underlying data field stays drawer_number (existing saved shifts
        # keep working) but the visible label must say Cashier number, not Drawer.
        self.assertNotIn('field("Drawer optional"', app)
        self.assertIn('field("Cashier number optional"', app)
        self.assertIn('data-field="drawer_number"', app)

    def test_completed_shifts_can_be_edited_in_place(self):
        html = (ROOT / "static" / "index.html").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        self.assertIn('id="masterEditBanner"', html)
        self.assertIn("data-edit-completed", app)
        self.assertIn("function openCompletedShiftForEdit", app)
        self.assertIn("function exitEditMode", app)
        self.assertIn("function finishEditingCompletedShift", app)
        self.assertIn("data-finish-edit", app)
        # Editing a completed shift must update that saved record in place,
        # keep the original completion date, and stamp when it was edited.
        self.assertIn("lastEditedAt", app)
        self.assertIn("lastEditedAt", logic)
        self.assertIn("originalCompletedAt", app)

    def test_check_number_and_tab_number_are_asked_for_once(self):
        app = (ROOT / "static" / "app.js").read_text()
        logic = (ROOT / "static" / "logic.js").read_text()
        self.assertIn('field("Check # / Tab #"', app)
        self.assertIn('field("Customer/SmartTab tip"', app)
        self.assertIn("Logic.pairedChipFields(tip,chip)", app)
        self.assertIn("Logic.pairShiftFields(state.shift.tipRows,state.shift.chipRows)", app)
        self.assertIn("Logic.pairShiftFields(snapshot.tipRows,snapshot.chipRows)", app)
        self.assertIn("Logic.pairShiftFields(state.viewingShift.tipRows,state.viewingShift.chipRows)", app)
        self.assertIn("chip.tab_number = checkNumber", logic)
        self.assertIn("chip.tip_smarttab = customerTip", logic)
        self.assertIn("check_number: checkNumber", logic)

    def test_customer_smarttab_tip_shows_dollar_sign_and_whole_dollars(self):
        app = (ROOT / "static" / "app.js").read_text()
        # The old field said "Customer tip / SmartTab tip" and accepted cents.
        # It must now say "Customer/SmartTab tip", show a leading $ sign, and
        # only ever hold whole dollar amounts (no cents).
        self.assertNotIn('field("Customer tip / SmartTab tip"', app)
        self.assertIn('field("Customer/SmartTab tip"', app)
        self.assertIn('class="money-prefix">$</span>', app)
        self.assertIn('data-field="tip_amount" value="${esc(tipDisplayAmount(tip))}" type="number" min="0" step="1" inputmode="numeric"', app)
        self.assertIn("function tipDisplayAmount", app)
        # Typed input is rounded to a whole dollar before it is stored, and the
        # visible box itself snaps to the whole number once the field blurs
        # (change event), not on every keystroke, so mid-typed decimals like
        # "42.5" are not mangled while the employee is still typing.
        self.assertIn('fieldName==="tip_amount"', app)
        self.assertIn("Math.round(Number(value))", app)
        self.assertIn('event.type==="change"', app)

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

    def test_club_and_cage_thirty_lines_still_fit_one_letter_page(self):
        css = (ROOT / "static" / "styles.css").read_text()
        # 30 rows plus a header row must fit inside an 8.5x11 letter page with
        # 0.3in margins on both sheets. Row height x 31 rows must stay under
        # roughly 7.9in (8.5in page minus 0.6in of margin, minus heading/brand
        # chrome above the table), so a fixed row height is required for both
        # the club and cage print tables now that both print 30 lines. Row
        # height was pushed up to ~0.21in/row for bold, larger print text.
        # This exact ceiling was found by rendering real 30/25-row PDFs with
        # every print font/size uniformly scaled up and checking actual page
        # count and page content (a naive per-rule bump caused a hidden
        # overflow: page count still read 3, but real rendering showed a
        # missing row and a bled-through duplicate brand mark). A uniform
        # 1.1x scale of the entire original print block was the verified
        # highest scale that renders exactly 3 clean pages with every row
        # intact; 1.15x already drops a row and duplicates the brand mark.
        match = re.search(r"@media print\{.*?\.club-paper-table th,\.club-paper-table td\{height:([\d.]+)in\}\.cage-paper-table th,\.cage-paper-table td\{height:([\d.]+)in\}", css, re.S)
        self.assertIsNotNone(match, "print row-height rule for club/cage tables is missing")
        club_row_in, cage_row_in = float(match.group(1)), float(match.group(2))
        self.assertLessEqual(club_row_in * 31, 7.9, "club table rows no longer fit one letter page at 30 lines")
        self.assertLessEqual(cage_row_in * 31, 7.9, "cage table rows no longer fit one letter page at 30 lines")

    def test_mid_shift_preview_does_not_shrink_below_readable_size(self):
        css = (ROOT / "static" / "styles.css").read_text()
        app = (ROOT / "static" / "app.js").read_text()
        # The mid-shift "View" preview used to be squeezed down with a
        # mobile-only font/padding shrink and no fixed width, so on a phone
        # screen a wide sheet like Club Dance Dollar Tips would clip column
        # headers ("Supervisor $" rendered as "Supervis"). The sheet must now
        # always render at its true full-size letter-page width (so it looks
        # exactly like the sheet that later prints) and then be visually
        # scaled down as a whole with a CSS transform so every column and row
        # stays visible and in proportion, instead of columns clipping or the
        # operator having to scroll to see the rest of the sheet.
        self.assertIn(".paper-landscape{width:1056px;aspect-ratio:11/8.5}", css)
        self.assertIn(".paper-portrait{width:816px;aspect-ratio:8.5/11}", css)
        self.assertIn("scalePreviewSheet", app)
        self.assertIn("sheet-scale-wrapper", app)
        self.assertIn("transform=`scale(", app)
        # The old mobile breakpoint used to shrink table row height, padding
        # and font size on every paper sheet; that rule must be gone so the
        # sheet the operator views mid-shift never differs from the sheet
        # that later prints, it is only ever scaled as a whole.
        self.assertNotIn(".paper-table th,.paper-table td{height:18px", css)
        # Print output must still stay unaffected: it forces width and
        # min-width back so a fixed-size letter page never gets scaled or an
        # unwanted scrollbar.
        self.assertIn("min-width:0!important", css)

    def test_generated_sheets_match_uploaded_paper_forms(self):
        app = (ROOT / "static" / "app.js").read_text()
        css = (ROOT / "static" / "styles.css").read_text()
        for title in ["CLUB DANCE DOLLAR TIPS", "SUPERVISOR TAB TOTALS", "CAGE SMARTTAB TIP TOTALS", "CHIP TOTALS SHEET"]:
            self.assertIn(title, app)
        for class_name in ["club-tips-form", "cage-smarttab-form", "chip-totals-form", "paper-field", "paper-total-row"]:
            self.assertIn(class_name, app)
        self.assertNotIn("paper-prev-row", app)
        self.assertNotIn("Prev Pg", app)
        self.assertNotIn("PRIOR PG", app)
        self.assertIn("paperRows(25", app)
        self.assertIn("paperRows(30", app)
        self.assertEqual(app.count("paperRows(30"), 2, "Club Dance Dollar Tips and Cage SmartTab both print 30 lines")
        self.assertIn("@page portrait-sheet", css)
        self.assertIn("@page landscape-sheet", css)
        self.assertIn("page:portrait-sheet", css)
        self.assertIn("page:landscape-sheet", css)
        self.assertIn("print-color-adjust:exact", css)

    def test_club_and_cage_sheets_have_a_narrow_line_number_column(self):
        app = (ROOT / "static" / "app.js").read_text()
        # Both sheets print one row per transaction line, and each line must
        # show its line number in a narrow leading column, matching what
        # every line number looked like on the two printed columns.
        match_club = re.search(r"function clubTipsForm\(source\)\{(.+?)\n\}", app, re.S)
        self.assertIsNotNone(match_club)
        club_body = match_club.group(1)
        self.assertIn("<th>#</th>", club_body)
        self.assertIn("<td>${index+1}</td>", club_body)
        self.assertIn('colspan="2"', club_body)

        match_cage = re.search(r"function cageSmartTabForm\(source\)\{(.+?)\n\}", app, re.S)
        self.assertIsNotNone(match_cage)
        cage_body = match_cage.group(1)
        self.assertIn("<th>#</th>", cage_body)
        self.assertIn("<td>${index+1}</td>", cage_body)
        self.assertIn('colspan="2"', cage_body)

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
        match = re.search(r"\.paper-total-row th:first-child\{([^}]*)\}", css)
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
        self.assertIn('const CACHE = "chip-tips-master-v21"', sw)
        for asset in ["./", "styles.css?v=21", "logic.js?v=21", "app.js?v=21", "manifest.webmanifest?v=21", "brand/peppermint-hippo-mark.png", "brand/peppermint-hippo-logo.png", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-192.png", "icons/icon-maskable-512.png"]:
            self.assertIn(f'"{asset}"', sw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
