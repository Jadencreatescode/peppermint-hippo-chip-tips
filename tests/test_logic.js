"use strict";
const assert = require("assert");
const logic = require("../static/logic.js");

assert.strictEqual(logic.amountToCents("12.45"), 1245);
assert.deepStrictEqual(logic.splitCents(223200), {supervisor:167400, cashier:55800});
assert.deepStrictEqual(logic.splitCents(1245), {supervisor:934, cashier:311});
assert.deepStrictEqual(logic.calculateRows([{tip_amount:"12.45"},{tip_amount:"20.00"}]), {tip:3245, supervisor:2434, cashier:811});

const chip = logic.calculateChipRow({
  chip_total_invoice:"520.00",
  room_fee_invoice:"25.00",
  check_total_without_tip:"999.00",
  tip_smarttab:"124.80",
});
assert.deepStrictEqual(chip, {
  chipInvoice:52000,
  chipWithFee:62400,
  roomFee:0,
  grandInvoice:62400,
  checkWithoutTip:62400,
  tipSmartTab:12480,
  finalInvoice:74880,
  totalWithTip:74880,
  difference:0,
});
const totals = logic.calculateChipTotals([
  {chip_total_invoice:"520",room_fee_invoice:"0",tip_smarttab:"124.80"},
  {chip_total_invoice:"300",room_fee_invoice:"0",tip_smarttab:"0"},
  {chip_total_invoice:"200",room_fee_invoice:"0",tip_smarttab:"0"},
]);
assert.strictEqual(totals.chipInvoice,102000);
assert.strictEqual(totals.chipWithFee,122400);
assert.strictEqual(totals.grandInvoice,122400);
assert.strictEqual(totals.checkWithoutTip,122400);
assert.strictEqual(totals.tipSmartTab,12480);
assert.strictEqual(totals.finalInvoice,134880);
assert.strictEqual(totals.totalWithTip,134880);
assert.strictEqual(totals.difference,0);

const completedSheetRows = [
  ["520", "124.80"], ["1520", "364.80"], ["400", "96"], ["300", "0"],
  ["920", "220.80"], ["760", "182.40"], ["300", "72"], ["1000", "240"],
  ["300", "72"], ["360", "86.40"], ["1520", "364.80"], ["200", "0"],
  ["500", "120"], ["1200", "288"],
].map(([chip_total_invoice, tip_smarttab]) => ({chip_total_invoice, tip_smarttab}));
const completedSheetTotals = logic.calculateChipTotals(completedSheetRows);
assert.strictEqual(completedSheetTotals.chipInvoice, 980000);
assert.strictEqual(completedSheetTotals.grandInvoice, 1176000);
assert.strictEqual(completedSheetTotals.checkWithoutTip, 1176000);
assert.strictEqual(completedSheetTotals.tipSmartTab, 223200);
assert.strictEqual(completedSheetTotals.totalWithTip, 1399200);

const tips = logic.printableTipRows([{customer_name:"Guest",drawer_number:"3",check_number:"11",tip_amount:"12.45",entry_type:"DD"},{}]);
assert.strictEqual(tips.length,1);
assert.strictEqual(tips[0].supervisor_cents,934);
const chips = logic.printableChipRows([{tab_number:"T1",chip_total_invoice:"100"},{}]);
assert.strictEqual(chips.length,1);
assert.strictEqual(chips[0].chipWithFee,12000);
assert.strictEqual(logic.hasChipData({check_total_without_tip:"99.00"}), false);
assert.strictEqual(logic.hasChipData({room_fee_invoice:"99.00"}), false);

assert.strictEqual(logic.isSharedTransfer("0406"), true);
assert.strictEqual(logic.isSharedTransfer("02"), true);
assert.strictEqual(logic.isSharedTransfer("03"), true);
assert.strictEqual(logic.isSharedTransfer("04"), true);
assert.strictEqual(logic.isSharedTransfer("06"), true);
assert.strictEqual(logic.isSharedTransfer("012345"), true);
assert.strictEqual(logic.isSharedTransfer("0"), true);
assert.strictEqual(logic.isSharedTransfer("406"), false);
assert.strictEqual(logic.isSharedTransfer("1203"), false);
assert.strictEqual(logic.isSharedTransfer("04A6"), false);
assert.strictEqual(logic.isSharedTransfer(""), false);

// Check number and tab number are one value, and the customer tip and the SmartTab
// tip are one value, so each is typed in once and lands in both printed columns.
const pairedTip = {check_number:"256", tip_amount:"20.00"};
const pairedChip = {transfer_to:"04", chip_total_invoice:"520"};
logic.pairedChipFields(pairedTip, pairedChip);
assert.strictEqual(pairedChip.tab_number, "256");
assert.strictEqual(pairedChip.tip_smarttab, "20.00");
assert.deepStrictEqual(logic.printableChipRows([pairedChip]), [{
  sequence:1, transfer_to:"04", tab_number:"256", chipInvoice:52000, chipWithFee:62400,
  roomFee:0, grandInvoice:62400, checkWithoutTip:62400, tipSmartTab:2000,
  finalInvoice:64400, totalWithTip:64400, difference:0,
}]);

logic.pairedChipFields({check_number:"", tip_amount:""}, pairedChip);
assert.strictEqual(pairedChip.tab_number, "");
assert.strictEqual(pairedChip.tip_smarttab, "");

const legacyTips = [{check_number:"", tip_amount:""}];
const legacyChips = [{tab_number:"812", tip_smarttab:"30"}];
logic.pairShiftFields(legacyTips, legacyChips);
assert.strictEqual(legacyTips[0].check_number, "812");
assert.strictEqual(legacyTips[0].tip_amount, "30");
assert.strictEqual(legacyChips[0].tab_number, "812");
assert.strictEqual(legacyChips[0].tip_smarttab, "30");

const typedTips = [{check_number:"257", tip_amount:"10"}];
const staleChips = [{tab_number:"81", tip_smarttab:"364.80"}];
logic.pairShiftFields(typedTips, staleChips);
assert.strictEqual(staleChips[0].tab_number, "257");
assert.strictEqual(staleChips[0].tip_smarttab, "10");
assert.deepStrictEqual(logic.pairShiftFields(null, null), {tipRows:[], chipRows:[]});

const routedTips = [
  {customer_name:"Shared", tip_amount:"30"},
  {customer_name:"Window", tip_amount:"20"},
];
const routedChips = [
  {transfer_to:"0406"},
  {transfer_to:"406"},
];
assert.deepStrictEqual(logic.calculateSharedTipTotals(routedTips, routedChips), {
  tip:3000, supervisor:2250, cashier:750,
});
assert.deepStrictEqual(logic.printableSharedTipRows(routedTips, routedChips).map(row => row.customer_name), ["Shared"]);
assert.strictEqual(logic.calculateRows(routedTips).tip, 5000);

const archived = logic.upsertCompletedShift([], {
  id:"shift-1", work_date:"2026-09-22", shift:"Night", tipRows:routedTips, chipRows:routedChips,
}, "archive-1", "2026-09-22T05:00:00.000Z");
assert.strictEqual(archived.length, 1);
assert.strictEqual(archived[0].id, "archive-1");
assert.strictEqual(archived[0].completedAt, "2026-09-22T05:00:00.000Z");
assert.strictEqual(archived[0].shift.tipRows[0].customer_name, "Shared");
routedTips[0].customer_name = "Changed after archive";
assert.strictEqual(archived[0].shift.tipRows[0].customer_name, "Shared", "completed shift must be a snapshot");
const updatedArchive = logic.upsertCompletedShift(archived, {
  id:"shift-1", work_date:"2026-09-22", shift:"Night", tipRows:[{customer_name:"Corrected"}], chipRows:routedChips,
}, "archive-1", "2026-09-22T06:00:00.000Z");
assert.strictEqual(updatedArchive.length, 1, "saving the same completed shift must update, not duplicate");
assert.strictEqual(updatedArchive[0].shift.tipRows[0].customer_name, "Corrected");
assert.strictEqual(updatedArchive[0].completedAt, "2026-09-22T06:00:00.000Z");

const blank = logic.blankShift("2026-09-21");
assert.strictEqual(blank.version,3);
assert.deepStrictEqual(blank.tipRows,[]);
assert.deepStrictEqual(blank.chipRows,[]);
console.log("All master sheet, tip split, chip fee, and reconciliation tests passed");
