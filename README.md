# Peppermint Hippo Chip Tips Tablet App

Chip Tips is an installable Peppermint Hippo Las Vegas Android and iPad worksheet app. Employees enter each shift in one Master Shift screen. The app uses the same red, black, cream, and hippo mark identity as the contractor app and generates three live worksheets from that single entry source:

1. Chip Tips
2. Cage SmartTab Tip Totals
3. Chip Totals Sheet

Shift information stays only in the tablet browser. No transaction data is sent to a server.

## Master Shift information

The shared header contains the date, shift, tip pool day, bank start time, bank end time, and people working.

The entry screen contains one transaction questionnaire. Each transaction holds all customer, receipt, customer tip, and chip invoice information needed by the three generated worksheets. Shared shift information stays above the transactions and is entered only once.

Each transaction contains customer, cashier number, check number and tab number, customer tip and SmartTab tip, cover or dance dollar type, card, location, host, time closed, Transfer To, and total chips. A numeric Transfer To value beginning with zero, such as 0406, identifies a shared tip. Shared transactions populate Chip Tips, Cage SmartTab Tip Totals, and Chip Totals Sheet, and their customer tips enter the fixed 75 percent supervisor and 25 percent cashier split. A normal Transfer To number identifies a separate cage window transaction. Separate transactions remain on Cage SmartTab Tip Totals and Chip Totals Sheet, but are excluded from Chip Tips and all shared tip totals. A blank or nonnumeric Transfer To value is treated as separate until corrected.

Check number and tab number are the same number, and customer tip and SmartTab tip are the same amount. The questionnaire therefore asks for each pair once, under the labels Check # / Tab # and Customer/SmartTab tip, and the single value is written into both printed columns. The customer and receipt side of the questionnaire is the source. Typing a check number or a customer tip fills the paired Chip Totals value immediately, and a newly added transaction starts with its pairs blank on both sides.

The Customer/SmartTab tip box shows a dollar sign in front of the amount and only accepts whole dollars, no cents, since tips are always counted and handed over in whole dollar bills.

Total chips is a chip count, not a typed dollar figure with cents: the cage only carries $20 and $100 chips, so every real total is a whole multiple of $20 and the field steps by $20. If an employee types an amount that is not a multiple of $20, the transaction shows a warning underneath the field ("Not a multiple of $20") so the mistake is caught before the shift is completed, instead of silently printing a total nobody could actually hand over in chips.

Room fee is not part of the questionnaire and is ignored even if an older saved shift contains a room fee value. The original Room Fee Invoice column remains blank on the generated Chip Totals Sheet so the output still matches the paper template. The app automatically calculates the chip total with the explicit 20 percent fee, Grand Total Invoice, Check Total Without Tip, Final Invoice including the entered SmartTab tip, Total With Tip SmartTab, and the printed checker equation. Grand Total Invoice and Check Total Without Tip use the same calculated amount, so employees do not enter the same value twice.

Older saved customer rows and chip rows are paired by row position when the unified questionnaire loads, preserving the existing entries without requiring reentry. Both directions are handled: if only the older chip row carries a tab number or SmartTab tip, that value fills the questionnaire field, so the printed sheets keep the old numbers instead of blanking them.

Both Club Dance Dollar Tips and Cage SmartTab Tip Totals print a narrow line number column, one number per printed line, so a specific row can always be pointed to by number instead of by scanning down the sheet. Both sheets print 30 lines, and both still fit on a single 8.5 by 11 inch letter page in landscape, the same as before the line-number column and the row count increase.

The completed reference sheet includes fourteen chip invoices totaling $9,800 and tips totaling $2,232. Applying the printed times 1.2 rule produces $11,760 before tips and $13,992 after tips. The handwritten $11,740 subtotal on the reference sheet does not reconcile with its rows or final total, so the app uses the mathematically correct $11,760 subtotal.

Cashier number is optional. It is the same field the paper Cage SmartTab form calls Drawer #, just relabeled to match how the cage actually talks about it: which cashier's drawer the chips came from.

Every Remove button opens a confirmation dialog that identifies the exact transaction or administration item. No direct remove button erases information immediately.

## Completed shifts and sheet package

Completing a shift saves an independent snapshot in Completed Shifts on the tablet. It does not erase the active shift. A completed shift can be reopened later to view or print the same three populated forms. Saving the same completed shift again updates its existing archived record instead of creating a duplicate.

An Edit button on every completed shift card lets an employee reopen it in the Master Shift screen and change anything: fix a typo, correct a chip count, adjust a tip. While editing, a banner at the top of Master Shift makes clear the changes are going to a saved record, not the live active shift, and a "Done editing" button returns to Home when finished. Every edit updates the record's "Edited" timestamp shown on its card, so there is always a record that the completed shift was touched after the fact, without losing the original completion date.

Starting a new shift is a separate action that becomes available only after the current shift has been archived. The new shift resets the entry screen while every completed shift remains available from Home.

The former emergency JSON download is not part of the shift workflow. Save three sheets as PDF opens the device print screen with exactly three populated pages: the landscape Club Dance Dollar Tips and Supervisor Tab Totals form, the landscape Cage SmartTab Tip Totals form, and the portrait Chip Totals Sheet form. These layouts reproduce the uploaded paper forms, including fixed blank rows, blocked regions, totals, the chip checker equation, and a restrained Peppermint Hippo identifier on each sheet. Earlier versions carried a "Prev Pg" / "PRIOR PG" row meant to hand a running total from one printed page to the next by hand. That row is gone: a multi-page shift now prints every page of a sheet in the same pass, so there is nothing left to carry forward.

## Printed sheet text alignment

Every label inside a sheet box prints upright and centred in its box, not rotated and not left or top aligned. The total labels, the header row of every table, and the checker line all follow that rule. Values sit in the middle of their column on all three sheets, so a money figure, a check number, a card type, or a customer name never presses against the left or right edge of its box. The print stylesheet forces horizontal writing direction for the total row's label cell, and the Chip Totals header row is taller than its data rows so the three line Grand Total Invoice header stays inside its own box instead of being cut off.

## App icon

The home screen icon is the CAGE sign uploaded by the club. It is generated from that image rather than drawn by hand, so the installed app shows the real sign artwork.

To regenerate every icon size from the uploaded sign:

```bash
uv run --with pillow python scripts/build_icons.py
```

The build crops the scan to the letters, clears the scan border lines and JPEG noise, and centres the wordmark on a white square. Android maskable icons are built with extra margin so the letters stay inside the circle that Android guarantees is visible after masking. The Apple touch icon carries no transparency, because iOS composites transparent areas onto black.

The icon files are `static/icons/icon-192.png`, `static/icons/icon-512.png`, `static/icons/icon-maskable-192.png`, `static/icons/icon-maskable-512.png`, and `static/icons/apple-touch-icon-180.png`. The original upload is kept at `assets/brand/cage-sign-source.jpeg`. The header still shows the Peppermint Hippo mark.

## Daily workflow

1. Open Master Shift.
2. Enter shared shift information once.
3. Add one transaction for each customer receipt and chip invoice.
4. Open Live Sheets at any time to check each generated worksheet and its current totals.
5. Print an individual worksheet when needed.
6. At the end of the shift, choose Complete and save shift.
7. Choose Save three sheets as PDF and select Save as PDF on the device print screen.
8. Start a new shift only when ready. The completed shift remains on Home.

## Responsive entry layout

Entry rows never require horizontal scrolling. Wide tablets use a compact line layout. Narrow phones automatically reflow each line into a small two column card while keeping every field visible.

## Preview

Run:

```bash
python3 server.py
```

Then open `http://127.0.0.1:8787`.

The preview server only serves static application files. Shift data remains in browser local storage.

## Tests

Run:

```bash
python3 -m unittest discover -s tests -v
```

Then run:

```bash
node tests/test_logic.js
```

Finally run the browserless application flow test:

```bash
node tests/test_runtime.js
```

The real browser flow and PDF verification use temporary test dependencies through `uv`:

```bash
uv run --with playwright python tests/test_browser.py
```

```bash
uv run --with pypdf --with pymupdf python tests/verify_pdf.py
```

The printed geometry test measures every cell of all three sheets in a real browser under print media, at the true page content width of each form, and fails if any text is rotated, clipped, or off centre:

```bash
uv run --with playwright python tests/test_print_geometry.py
```

`tests/probe_label_metrics.py` prints the raw measurements for the total rows of each sheet, which is the quickest way to investigate one cell that looks wrong.
