const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const nodes = Object.fromEntries([
  "#transactionRows",
  "#totalTips",
  "#chipInvoiceTotal",
  "#finalInvoiceTotal",
].map(selector => [selector, { innerHTML: "", textContent: "" }]));

const context = {
  console,
  Date,
  Intl,
  Math,
  JSON,
  Number,
  String,
  Object,
  Array,
  Set,
  Blob,
  setTimeout,
  clearTimeout,
  localStorage: { getItem: () => null, setItem: () => {} },
  history: { replaceState: () => {} },
  location: { hash: "" },
  navigator: {},
  document: {
    querySelector: selector => nodes[selector] || null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    visibilityState: "visible",
  },
  addEventListener: () => {},
};
context.window = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, "static", "logic.js"), "utf8"), context);
vm.runInContext(fs.readFileSync(path.join(root, "static", "app.js"), "utf8"), context);

const result = vm.runInContext(`(() => {
  state.config = defaultConfig();
  state.shift = {
    ...Logic.blankShift("2026-09-22"),
    shift: "Night",
    tip_pool_day: "Tuesday",
    workers: ["Employee 1"],
    tipRows: [{
      id: "tip-1",
      customer_name: "Jordan",
      drawer_number: "4",
      check_number: "812",
      tip_amount: "30",
      entry_type: "DD",
      card_type: "Visa",
      location: "VIP Room",
      host: "Host 1",
      time_closed: "23:10",
    }, {
      id: "tip-2",
      customer_name: "Window Guest",
      drawer_number: "5",
      check_number: "813",
      tip_amount: "20",
      entry_type: "DD",
      card_type: "Mastercard",
      location: "Main Floor",
      host: "Host 2",
      time_closed: "23:20",
    }],
    chipRows: [{
      id: "chip-1",
      transfer_to: "0406",
      tab_number: "T42",
      chip_total_invoice: "100",
      room_fee_invoice: "999",
      tip_smarttab: "24",
    }, {
      id: "chip-2",
      transfer_to: "406",
      tab_number: "T43",
      chip_total_invoice: "50",
      tip_smarttab: "12",
    }],
  };
  const originalTip = state.shift.tipRows[1];
  alignTransactionRows();
  const paired = state.shift.tipRows.length === 2 && state.shift.chipRows.length === 2 && state.shift.tipRows[1] === originalTip;
  renderTransactionRows();
  return {
    paired,
    entry: document.querySelector("#transactionRows").innerHTML,
    chipTips: generatedSheetHtml("chip-tips"),
    cage: generatedSheetHtml("cage"),
    chipTotals: generatedSheetHtml("chip-totals"),
    totalTips: document.querySelector("#totalTips").textContent,
    chipInvoiceTotal: document.querySelector("#chipInvoiceTotal").textContent,
    finalInvoiceTotal: document.querySelector("#finalInvoiceTotal").textContent,
    pairedChipState: state.shift.chipRows[0].tab_number + "|" + state.shift.chipRows[0].tip_smarttab,
  };
})()`, context);

assert.strictEqual(result.paired, true, "existing rows should stay paired by row position");
for (const value of ["Jordan", "812", "100", "30"]) assert(result.entry.includes(value), value);
assert(!result.entry.includes('data-field="tab_number"'));
assert(!result.entry.includes('data-field="tip_smarttab"'));
assert(result.entry.includes("Check # / Tab #"));
assert(result.entry.includes("Customer/SmartTab tip"));
assert.strictEqual(result.pairedChipState, "812|30", "check number and customer tip fill the tab number and SmartTab tip");
assert(!result.entry.includes("Room fee"));
assert(result.chipTips.includes("Jordan"));
assert(!result.chipTips.includes("Window Guest"));
assert(result.chipTips.includes("$30.00"));
assert(result.chipTips.includes("$22.50"));
assert(result.chipTips.includes("$7.50"));
assert(result.cage.includes("Jordan"));
assert(result.cage.includes("812"));
assert(result.cage.includes("Window Guest"));
assert(result.cage.includes("$50.00"));
assert(result.chipTotals.includes("812"));
assert(result.chipTotals.includes("813"));
assert(!result.chipTotals.includes("T42"));
assert(!result.chipTotals.includes("T43"));
assert(result.chipTotals.includes("$150.00"));
assert(result.chipTotals.includes("$180.00"));
assert(result.chipTotals.includes("$30.00"));
assert(result.chipTotals.includes("$20.00"));
assert(result.chipTotals.includes("$230.00"));
assert(!result.chipTotals.includes("$24.00"));
assert(!result.chipTotals.includes("$999.00"));
assert.strictEqual(result.totalTips, "$30.00");
assert.strictEqual(result.chipInvoiceTotal, "$150.00");
assert.strictEqual(result.finalInvoiceTotal, "$230.00");
assert(result.entry.includes("Shared tip"));
assert(result.entry.includes("Separate tip"));
console.log("Shared and separate transactions routed correctly, the check number and customer tip filled both sheets, and legacy room fee data was ignored");
