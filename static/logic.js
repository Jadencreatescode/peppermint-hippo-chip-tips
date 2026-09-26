(function (root, factory) {
  const logic = factory();
  if (typeof module === "object" && module.exports) module.exports = logic;
  root.ChipTipsLogic = logic;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function amountToCents(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount <= 0) return 0;
    return Math.round(amount * 100);
  }

  function splitCents(cents) {
    const safe = Math.max(0, Math.round(Number(cents) || 0));
    const supervisor = Math.round(safe * 0.75);
    return { supervisor, cashier: safe - supervisor };
  }

  function calculateRows(rows) {
    return (Array.isArray(rows) ? rows : []).reduce((totals, row) => {
      const tip = amountToCents(row.tip_amount);
      const split = splitCents(tip);
      totals.tip += tip;
      totals.supervisor += split.supervisor;
      totals.cashier += split.cashier;
      return totals;
    }, { tip: 0, supervisor: 0, cashier: 0 });
  }

  function calculateChipRow(row) {
    const chipInvoice = amountToCents(row?.chip_total_invoice);
    const chipWithFee = Math.round(chipInvoice * 1.2);
    const roomFee = 0;
    const grandInvoice = chipWithFee;
    const checkWithoutTip = grandInvoice;
    const tipSmartTab = amountToCents(row?.tip_smarttab);
    const finalInvoice = grandInvoice + tipSmartTab;
    const totalWithTip = finalInvoice;
    return { chipInvoice, chipWithFee, roomFee, grandInvoice, checkWithoutTip, tipSmartTab, finalInvoice, totalWithTip, difference: 0 };
  }

  function calculateChipTotals(rows) {
    return (Array.isArray(rows) ? rows : []).reduce((totals, row) => {
      const values = calculateChipRow(row);
      for (const key of Object.keys(totals)) totals[key] += values[key];
      return totals;
    }, { chipInvoice:0, chipWithFee:0, roomFee:0, grandInvoice:0, checkWithoutTip:0, tipSmartTab:0, finalInvoice:0, totalWithTip:0, difference:0 });
  }

  function hasTipData(row) {
    if (!row || typeof row !== "object") return false;
    return amountToCents(row.tip_amount) > 0 || ["customer_name","drawer_number","check_number","card_type","time_closed","entry_type","location","host"].some(key => String(row[key] || "").trim());
  }

  function hasChipData(row) {
    if (!row || typeof row !== "object") return false;
    return ["transfer_to","tab_number","chip_total_invoice","tip_smarttab"].some(key => String(row[key] || "").trim());
  }

  function isSharedTransfer(value) {
    return /^0\d*$/.test(String(value == null ? "" : value).trim());
  }

  function sharedTipRows(tipRows, chipRows) {
    const tips = Array.isArray(tipRows) ? tipRows : [];
    const chips = Array.isArray(chipRows) ? chipRows : [];
    return tips.filter((row, index) => isSharedTransfer(chips[index]?.transfer_to));
  }

  function calculateSharedTipTotals(tipRows, chipRows) {
    return calculateRows(sharedTipRows(tipRows, chipRows));
  }

  function cleanText(value, limit = 300) {
    return String(value == null ? "" : value).trim().slice(0, limit);
  }

  // The club writes one number for the receipt check and the SmartTab tab, and one
  // amount for the customer tip and the SmartTab tip. The questionnaire therefore
  // asks for each pair once, and both printed columns are filled from that value.
  function pairedChipFields(tipRow, chipRow) {
    const tip = tipRow && typeof tipRow === "object" ? tipRow : {};
    const chip = chipRow && typeof chipRow === "object" ? chipRow : {};
    const checkNumber = cleanText(tip.check_number, 60);
    const customerTip = cleanText(tip.tip_amount, 40);
    chip.tab_number = checkNumber;
    chip.tip_smarttab = customerTip;
    return { check_number: checkNumber, tip_amount: customerTip };
  }

  function pairShiftFields(tipRows, chipRows) {
    const tips = Array.isArray(tipRows) ? tipRows : [];
    const chips = Array.isArray(chipRows) ? chipRows : [];
    chips.forEach((chip, index) => {
      const tip = tips[index];
      if (!tip || typeof tip !== "object") return;
      if (!cleanText(tip.check_number, 60)) tip.check_number = cleanText(chip && chip.tab_number, 60);
      if (!cleanText(tip.tip_amount, 40)) tip.tip_amount = cleanText(chip && chip.tip_smarttab, 40);
      pairedChipFields(tip, chip);
    });
    return { tipRows: tips, chipRows: chips };
  }

  function printableTipRows(rows) {
    return (Array.isArray(rows) ? rows : []).filter(hasTipData).map(row => {
      const tipCents = amountToCents(row.tip_amount);
      const split = splitCents(tipCents);
      return {
        customer_name:cleanText(row.customer_name,120), drawer_number:cleanText(row.drawer_number,40),
        check_number:cleanText(row.check_number,60), card_type:cleanText(row.card_type,80),
        time_closed:cleanText(row.time_closed,20), entry_type:cleanText(row.entry_type,20),
        location:cleanText(row.location,80), host:cleanText(row.host,80), tip_cents:tipCents,
        supervisor_cents:split.supervisor, cashier_cents:split.cashier,
      };
    });
  }

  function printableSharedTipRows(tipRows, chipRows) {
    return printableTipRows(sharedTipRows(tipRows, chipRows));
  }

  function printableChipRows(rows) {
    return (Array.isArray(rows) ? rows : []).filter(hasChipData).map((row,index) => ({
      sequence:index + 1, transfer_to:cleanText(row.transfer_to,40), tab_number:cleanText(row.tab_number,60),
      ...calculateChipRow(row),
    }));
  }

  function upsertCompletedShift(archives, shift, archiveId, completedAt) {
    const current = Array.isArray(archives) ? archives : [];
    const snapshot = JSON.parse(JSON.stringify(shift && typeof shift === "object" ? shift : {}));
    const record = { id:cleanText(archiveId,120), completedAt:cleanText(completedAt,80), shift:snapshot };
    return [record, ...current.filter(item => item && item.id !== record.id)]
      .sort((a,b) => String(b.completedAt || "").localeCompare(String(a.completedAt || "")));
  }

  function blankShift(dateValue) {
    return {
      version:3, work_date:dateValue || "", shift:"", tip_pool_day:"", workers:[],
      bank_start_time:"", bank_end_time:"", tipRows:[], chipRows:[], savedAt:"", reportOpenedAt:"",
    };
  }

  return { amountToCents, splitCents, calculateRows, calculateChipRow, calculateChipTotals, hasTipData, hasChipData, isSharedTransfer, calculateSharedTipTotals, cleanText, pairedChipFields, pairShiftFields, printableTipRows, printableSharedTipRows, printableChipRows, upsertCompletedShift, blankShift };
});
