const Logic = window.ChipTipsLogic;
const CONFIG_KEY = "chip_tips_tablet_config_v2";
const SHIFT_KEY = "chip_tips_active_shift_v2";
const ARCHIVE_KEY = "chip_tips_completed_shifts_v1";
const state = {
  config:null,
  shift:null,
  archives:[],
  viewingShift:null,
  viewingArchiveId:null,
  editingArchiveId:null,
  activeShiftBeforeEdit:null,
  currentSheet:"chip-tips",
  deferredInstall:null,
  saveTimer:null,
  pendingRemoval:null,
};
const $ = (selector,root=document) => root.querySelector(selector);
const $$ = (selector,root=document) => [...root.querySelectorAll(selector)];
const uid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(16).slice(2)}`;
const esc = (value="") => String(value).replace(/[&<>'"]/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[ch]);
const today = () => {const n=new Date(),o=n.getTimezoneOffset();return new Date(n.getTime()-o*60000).toISOString().slice(0,10);};
const money = cents => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format((cents||0)/100);
const option = value => ({id:uid(),value});
const clone = value => JSON.parse(JSON.stringify(value));

function defaultConfig(){
  return {version:3,options:{
    employees:["Employee 1","Employee 2"].map(option),
    hosts:["Host 1","Host 2"].map(option),
    locations:["Main Floor","VIP Room","Patio"].map(option),
    card_types:["Visa","Mastercard","American Express","Discover"].map(option),
    shifts:["Day","Swing","Night"].map(option),
    tip_pool_days:["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map(option),
  }};
}
function newTipRow(){return{id:uid(),customer_name:"",drawer_number:"",check_number:"",tip_amount:"",entry_type:"DD",card_type:"",location:"",host:"",time_closed:""};}
function newChipRow(){return{id:uid(),transfer_to:"",tab_number:"",chip_total_invoice:"",tip_smarttab:""};}
function newShift(){
  const shift=Logic.blankShift(today());
  shift.id=uid();
  shift.tipRows=[newTipRow(),newTipRow(),newTipRow()];
  shift.chipRows=[newChipRow(),newChipRow(),newChipRow()];
  return shift;
}
function alignTransactionRows(){
  if(!Array.isArray(state.shift.tipRows))state.shift.tipRows=[];
  if(!Array.isArray(state.shift.chipRows))state.shift.chipRows=[];
  const count=Math.max(state.shift.tipRows.length,state.shift.chipRows.length,1);
  while(state.shift.tipRows.length<count)state.shift.tipRows.push(newTipRow());
  while(state.shift.chipRows.length<count)state.shift.chipRows.push(newChipRow());
  Logic.pairShiftFields(state.shift.tipRows,state.shift.chipRows);
}
function parseStored(key,fallback){
  try{const value=JSON.parse(localStorage.getItem(key));return value&&typeof value==="object"?value:fallback;}catch{return fallback;}
}
function migrateShift(raw){
  if(!raw||typeof raw!=="object")return newShift();
  if(raw.version===3&&Array.isArray(raw.tipRows)){
    raw.id=raw.id||uid();
    return raw;
  }
  const next=Logic.blankShift(raw.work_date||today());
  next.id=raw.id||uid();
  for(const key of ["shift","tip_pool_day","savedAt","reportOpenedAt","bank_start_time","bank_end_time"])next[key]=raw[key]||"";
  next.workers=Array.isArray(raw.workers)?raw.workers:[];
  next.tipRows=(Array.isArray(raw.chipRows)?raw.chipRows:[]).map(row=>({...newTipRow(),...row,id:row.id||uid(),entry_type:row.entry_type||"DD",drawer_number:row.drawer_number||""}));
  if(!next.tipRows.length)next.tipRows=[newTipRow(),newTipRow(),newTipRow()];
  next.chipRows=[newChipRow(),newChipRow(),newChipRow()];
  return next;
}
function loadState(){
  state.config=parseStored(CONFIG_KEY,defaultConfig());
  if(!state.config.options)state.config=defaultConfig();
  for(const key of ["employees","hosts","locations","card_types","shifts","tip_pool_days"])if(!Array.isArray(state.config.options[key]))state.config.options[key]=[];
  state.config.version=3;
  state.shift=migrateShift(parseStored(SHIFT_KEY,null));
  state.archives=parseStored(ARCHIVE_KEY,[]);
  if(!Array.isArray(state.archives))state.archives=[];
  if(!Array.isArray(state.shift.tipRows)||!state.shift.tipRows.length)state.shift.tipRows=[newTipRow(),newTipRow(),newTipRow()];
  if(!Array.isArray(state.shift.chipRows)||!state.shift.chipRows.length)state.shift.chipRows=[newChipRow(),newChipRow(),newChipRow()];
  alignTransactionRows();
  saveConfig();
  saveLocal(false);
}
function saveConfig(){localStorage.setItem(CONFIG_KEY,JSON.stringify(state.config));}
function saveArchives(){localStorage.setItem(ARCHIVE_KEY,JSON.stringify(state.archives));}
function saveLocal(show=false){
  state.shift.savedAt=new Date().toISOString();
  if(state.editingArchiveId){
    const existing=state.archives.find(item=>item.id===state.editingArchiveId);
    const originalCompletedAt=existing?existing.completedAt:new Date().toISOString();
    state.shift.archive_id=state.editingArchiveId;
    state.shift.lastEditedAt=new Date().toISOString();
    state.archives=Logic.upsertCompletedShift(state.archives,state.shift,state.editingArchiveId,originalCompletedAt);
    saveArchives();
    if(show)toast("Completed shift updated");
  }else{
    localStorage.setItem(SHIFT_KEY,JSON.stringify(state.shift));
    renderActiveShift();
    if(show)toast("Shift saved on this tablet");
  }
}
function scheduleSave(){
  clearTimeout(state.saveTimer);
  if($("#saveStatus"))$("#saveStatus").textContent=state.editingArchiveId?"Updating completed shift…":"Saving…";
  state.saveTimer=setTimeout(()=>{saveLocal(false);if($("#saveStatus"))$("#saveStatus").textContent=state.editingArchiveId?"Completed shift updated":"Saved on this tablet";},300);
}
function toast(message,error=false){
  const node=$("#toast");
  if(!node)return;
  node.textContent=message;
  node.classList.toggle("error",error);
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer=setTimeout(()=>node.classList.remove("show"),3000);
}

function showPage(name){
  if(name!=="master"&&state.editingArchiveId)exitEditMode();
  $$(".page").forEach(page=>page.classList.toggle("active",page.id===`page-${name}`));
  $$(".nav-button").forEach(button=>button.classList.toggle("active",button.dataset.page===name));
  if(name==="home")renderHome();
  if(name==="master"&&!state.editingArchiveId){state.viewingShift=null;state.viewingArchiveId=null;renderMaster();}
  else if(name==="master")renderMaster();
  if(name==="sheets")renderSheets();
  if(name==="close")renderClose();
  if(name==="admin")renderAdmin();
  window.scrollTo?.({top:0,behavior:"smooth"});
  history.replaceState(null,"",`#${name}`);
}
function optionSelect(id,category,placeholder,selected){
  $(id).innerHTML=`<option value="">${esc(placeholder)}</option>`+state.config.options[category].map(item=>`<option value="${esc(item.value)}" ${item.value===selected?"selected":""}>${esc(item.value)}</option>`).join("");
}
function workerChips(){
  const list=state.config.options.employees;
  $("#workerChoices").innerHTML=list.length?list.map(item=>`<label class="choice-chip"><input type="checkbox" value="${esc(item.value)}" ${state.shift.workers.includes(item.value)?"checked":""}><span>${esc(item.value)}</span></label>`).join(""):`<p class="empty-state">Add employee names in Admin.</p>`;
}
function renderHome(){renderActiveShift();renderCompletedShifts();}
function renderActiveShift(){
  const root=$("#activeShiftCard");
  if(!root||!state.shift)return;
  const tips=Logic.printableTipRows(state.shift.tipRows),chips=Logic.printableChipRows(state.shift.chipRows),transactions=Math.max(tips.length,chips.length),totals=Logic.calculateSharedTipTotals(state.shift.tipRows,state.shift.chipRows);
  const completed=state.shift.archive_id&&state.archives.some(item=>item.id===state.shift.archive_id);
  root.innerHTML=`<div><span class="status-dot ${completed?"complete":""}"></span><div><strong>${completed?"Completed shift still open":"Active shift"}</strong><p>${esc(state.shift.work_date||"No date")} · ${esc(state.shift.shift||"Shift not selected")} · ${transactions} transactions</p></div></div><div><strong>${money(totals.tip)}</strong><button data-page="${completed?"close":"master"}">${completed?"View saved status":"Continue"}</button></div>`;
}
function renderCompletedShifts(){
  const root=$("#completedShiftList");
  if(!root)return;
  if(!state.archives.length){root.innerHTML=`<div class="empty-state completed-empty"><strong>No completed shifts yet.</strong><p>Completed shifts will stay here with all three populated sheets.</p></div>`;return;}
  root.innerHTML=state.archives.map(record=>{
    const shift=record.shift||{},tips=Logic.calculateSharedTipTotals(shift.tipRows,shift.chipRows),chips=Logic.calculateChipTotals(shift.chipRows);
    return `<article class="completed-shift-card"><div><small>Completed ${esc(formatTimestamp(record.completedAt))}${shift.lastEditedAt?` · Edited ${esc(formatTimestamp(shift.lastEditedAt))}`:""}</small><h3>${esc(shift.work_date||"No date")} · ${esc(shift.shift||"Shift not selected")}</h3><p>${esc((shift.workers||[]).join(", ")||"No people listed")}</p></div><div class="completed-shift-totals"><span>Shared tips <strong>${money(tips.tip)}</strong></span><span>Chip total <strong>${money(chips.finalInvoice)}</strong></span></div><div class="completed-shift-actions"><button class="secondary-button" data-open-completed="${esc(record.id)}">Open three sheets</button><button class="secondary-button" data-edit-completed="${esc(record.id)}">Edit</button><button class="primary-button" data-print-completed="${esc(record.id)}">Save PDF again</button></div></article>`;
  }).join("");
}
function formatTimestamp(value){
  const date=new Date(value||"");
  return Number.isNaN(date.getTime())?"":date.toLocaleString([],{month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"});
}
function syncHeader(){
  state.shift.work_date=$("#workDate").value;
  state.shift.shift=$("#shiftName").value;
  state.shift.tip_pool_day=$("#tipPoolDay").value;
  state.shift.bank_start_time=$("#bankStart").value;
  state.shift.bank_end_time=$("#bankEnd").value;
  state.shift.workers=$$("#workerChoices input:checked").map(input=>input.value);
  scheduleSave();
}
function renderMaster(){
  $("#workDate").value=state.shift.work_date||today();
  optionSelect("#shiftName","shifts","Choose shift",state.shift.shift);
  optionSelect("#tipPoolDay","tip_pool_days","Choose day",state.shift.tip_pool_day);
  $("#bankStart").value=state.shift.bank_start_time||"";
  $("#bankEnd").value=state.shift.bank_end_time||"";
  workerChips();
  alignTransactionRows();
  renderTransactionRows();
  $("#saveStatus").textContent=state.editingArchiveId?"Editing completed shift":"Saved on this tablet";
  $("#masterEditBanner").innerHTML=state.editingArchiveId?`<div class="saved-source-banner"><div><strong>Editing a completed shift</strong><p>Changes here update the permanent record in Completed Shifts. The date and time of this edit are kept on the record.</p></div><button class="secondary-button" data-finish-edit>Done editing</button></div>`:"";
}
function field(label,html,cls=""){return`<label class="cell ${cls}"><small>${label}</small>${html}</label>`;}
function chipDenomHint(chip){
  if(!chip.chip_total_invoice)return"";
  return Logic.chipAmountMatchesDenominations(chip.chip_total_invoice)?"":"Not a multiple of $20 \u2014 chips only come in $20s and $100s.";
}
function renderTransactionRows(){
  alignTransactionRows();
  $("#transactionRows").innerHTML=state.shift.tipRows.map((tip,index)=>{
    const chip=state.shift.chipRows[index],shared=Logic.isSharedTransfer(chip.transfer_to),split=shared?Logic.splitCents(Logic.amountToCents(tip.tip_amount)):{supervisor:0,cashier:0},calculated=Logic.calculateChipRow(chip);
    return `<article class="transaction-row" data-index="${index}"><header class="transaction-row-header"><div><span>Transaction ${index+1}</span><strong>${esc(tip.customer_name||chip.tab_number||"New transaction")}</strong></div><button type="button" class="remove-row" data-remove-transaction="${index}" aria-label="Remove transaction ${index+1}">Remove</button></header><div class="transaction-groups"><fieldset class="transaction-group"><legend>Customer and receipt</legend><div class="transaction-grid customer-grid">${field("Customer",`<input data-field="customer_name" value="${esc(tip.customer_name)}">`,"wide-field")}${field("Cashier number optional",`<input data-field="drawer_number" value="${esc(tip.drawer_number)}" inputmode="numeric">`)}${field("Check # / Tab #",`<input data-field="check_number" value="${esc(tip.check_number)}" inputmode="numeric">`)}${field("Customer tip / SmartTab tip",`<input data-field="tip_amount" value="${esc(tip.tip_amount)}" type="number" min="0" step="0.01" inputmode="decimal">`)}${field("Cover or DD",`<select data-field="entry_type"><option value="C" ${tip.entry_type==="C"?"selected":""}>Cover</option><option value="DD" ${tip.entry_type==="DD"?"selected":""}>DD</option></select>`)}${field("Card",`<select data-field="card_type"><option value="">Choose</option>${state.config.options.card_types.map(item=>`<option value="${esc(item.value)}" ${item.value===tip.card_type?"selected":""}>${esc(item.value)}</option>`).join("")}</select>`)}${field("Location",`<select data-field="location"><option value="">Choose</option>${state.config.options.locations.map(item=>`<option value="${esc(item.value)}" ${item.value===tip.location?"selected":""}>${esc(item.value)}</option>`).join("")}</select>`)}${field("Host",`<select data-field="host"><option value="">Choose</option>${state.config.options.hosts.map(item=>`<option value="${esc(item.value)}" ${item.value===tip.host?"selected":""}>${esc(item.value)}</option>`).join("")}</select>`)}${field("Closed",`<input data-field="time_closed" value="${esc(tip.time_closed)}" type="time">`)}</div></fieldset><fieldset class="transaction-group chip-group"><legend>Chip totals</legend><div class="transaction-grid chip-grid">${field("Transfer To",`<input data-field="transfer_to" value="${esc(chip.transfer_to)}" inputmode="numeric" pattern="[0-9]*" placeholder="0406 for shared">`)}${field("Total chips ($20s / $100s)",`<input data-field="chip_total_invoice" value="${esc(chip.chip_total_invoice)}" type="number" min="0" step="20" inputmode="numeric">`)}</div><p class="chip-pair-note">Tab # and SmartTab tip carry the same value as Check # and Customer tip, so each one is typed in once and fills both sheets.</p><p class="chip-pair-note ${chipDenomHint(chip)?"chip-denom-warning":""}" data-result="chipDenomHint">${esc(chipDenomHint(chip))}</p><div class="transaction-result"><span class="sharing-status ${shared?"shared":"separate"}" data-result="sharingStatus"><strong>${shared?"Shared tip":"Separate tip"}</strong><small>${shared?"Transfer To starts with 0":"Not added to 75 / 25 totals"}</small></span><span>Supervisor 75% <strong data-result="supervisor">${money(split.supervisor)}</strong></span><span>Cashier 25% <strong data-result="cashier">${money(split.cashier)}</strong></span><span>Grand invoice <strong data-result="grandInvoice">${money(calculated.grandInvoice)}</strong></span><span>Total with tip <strong data-result="totalWithTip">${money(calculated.totalWithTip)}</strong></span></div></fieldset></div></article>`;
  }).join("");
  updateAllTotals();
}
function updateAllTotals(){
  const tips=Logic.calculateSharedTipTotals(state.shift.tipRows,state.shift.chipRows),chips=Logic.calculateChipTotals(state.shift.chipRows);
  $("#totalTips").textContent=money(tips.tip);
  $("#chipInvoiceTotal").textContent=money(chips.chipInvoice);
  $("#finalInvoiceTotal").textContent=money(chips.finalInvoice);
}
function addTransaction(){state.shift.tipRows.push(newTipRow());state.shift.chipRows.push(newChipRow());renderTransactionRows();scheduleSave();}
const tipFieldNames=new Set(["customer_name","drawer_number","check_number","tip_amount","entry_type","card_type","location","host","time_closed"]);
function updateTransactionInput(event){
  const row=event.target.closest(".transaction-row"),fieldName=event.target.dataset.field;
  if(!row||!fieldName)return;
  const index=Number(row.dataset.index),tip=state.shift.tipRows[index],chip=state.shift.chipRows[index];
  if(!tip||!chip)return;
  (tipFieldNames.has(fieldName)?tip:chip)[fieldName]=event.target.value;
  if(fieldName==="check_number"||fieldName==="tip_amount")Logic.pairedChipFields(tip,chip);
  const shared=Logic.isSharedTransfer(chip.transfer_to),split=shared?Logic.splitCents(Logic.amountToCents(tip.tip_amount)):{supervisor:0,cashier:0},calculated=Logic.calculateChipRow(chip),status=$('[data-result="sharingStatus"]',row);
  status.className=`sharing-status ${shared?"shared":"separate"}`;
  status.innerHTML=`<strong>${shared?"Shared tip":"Separate tip"}</strong><small>${shared?"Transfer To starts with 0":"Not added to 75 / 25 totals"}</small>`;
  $('[data-result="supervisor"]',row).textContent=money(split.supervisor);
  $('[data-result="cashier"]',row).textContent=money(split.cashier);
  $('[data-result="grandInvoice"]',row).textContent=money(calculated.grandInvoice);
  $('[data-result="totalWithTip"]',row).textContent=money(calculated.totalWithTip);
  $('[data-result="chipDenomHint"]',row).textContent=chipDenomHint(chip);
  $('[data-result="chipDenomHint"]',row).classList.toggle("chip-denom-warning",!!chipDenomHint(chip));
  updateAllTotals();
  scheduleSave();
}

const sheetDefinitions=[
  {id:"chip-tips",title:"Club Dance Dollar Tips",description:"Supervisor and cashier tip split"},
  {id:"cage",title:"Cage SmartTab Tip Totals",description:"Cover and dance dollar tip log"},
  {id:"chip-totals",title:"Chip Totals Sheet",description:"Chip invoice and SmartTab reconciliation"},
];
function sheetSource(){return state.viewingShift||state.shift;}
function renderSheets(){
  clearTimeout(state.saveTimer);
  if(!state.viewingShift)saveLocal(false);
  const source=sheetSource(),sharedTipTotals=Logic.calculateSharedTipTotals(source.tipRows,source.chipRows),cageTipTotals=Logic.calculateRows(source.tipRows),chipTotals=Logic.calculateChipTotals(source.chipRows);
  $("#sheetSaveStatus").textContent=state.viewingShift?"Saved completed shift":"Live from Master Shift";
  $("#sheetSourceBanner").innerHTML=state.viewingShift?`<div class="saved-source-banner"><div><strong>Viewing completed shift</strong><p>${esc(source.work_date||"No date")} · ${esc(source.shift||"Shift not selected")}. This is the saved snapshot.</p></div><button class="secondary-button" data-use-active-shift>Return to active shift</button></div>`:"";
  $("#generatedCards").innerHTML=sheetDefinitions.map(definition=>{
    const total=definition.id==="chip-tips"?money(sharedTipTotals.tip):definition.id==="cage"?money(cageTipTotals.tip):money(chipTotals.finalInvoice);
    return `<article class="generated-card ${state.currentSheet===definition.id?"selected":""}"><div><small>Current total</small><strong>${total}</strong></div><h2>${definition.title}</h2><p>${definition.description}</p><div><button data-view-sheet="${definition.id}" class="secondary-button">View</button><button data-print-sheet="${definition.id}" class="primary-button">Print</button></div></article>`;
  }).join("");
  renderGeneratedPreview();
}
function paperField(label,value){return`<span class="paper-field"><small>${label}</small><strong>${esc(value||"")}</strong></span>`;}
function paperBrand(){return`<div class="paper-brand"><img src="brand/peppermint-hippo-mark.png" alt=""><span><strong>PEPPERMINT HIPPO</strong><small>LAS VEGAS</small></span></div>`;}
function paperRows(count,rows,renderer){return Array.from({length:Math.max(count,rows.length)},(_,index)=>renderer(rows[index],index)).join("");}
function paperMoney(cents){return cents?money(cents):"";}
function clubTipsForm(source){
  const tips=Logic.printableSharedTipRows(source.tipRows,source.chipRows),totals=Logic.calculateSharedTipTotals(source.tipRows,source.chipRows);
  const rows=paperRows(20,tips,(row)=>`<tr><td>${esc(row?.customer_name||"")}</td><td>${esc(row?.check_number||"")}</td><td>${paperMoney(row?.tip_cents)}</td><td>${paperMoney(row?.supervisor_cents)}</td><td>${paperMoney(row?.cashier_cents)}</td><td>${esc(row?.card_type||"")}</td><td>${esc(row?.location||"")}</td><td>${esc(row?.host||"")}</td><td>${esc(row?.time_closed||"")}</td></tr>`);
  return `<div class="paper-sheet paper-landscape club-tips-form">${paperBrand()}<div class="club-form-heading"><div><h2>CLUB DANCE DOLLAR TIPS</h2>${paperField("Names",(source.workers||[]).join(", "))}</div><div>${paperField("Date",source.work_date)}${paperField("Shift",source.shift)}</div><div><h2>SUPERVISOR TAB TOTALS</h2>${paperField("Tip Pool Day",source.tip_pool_day)}</div></div><table class="paper-table club-paper-table"><thead><tr><th>Customer Name</th><th>Check #</th><th>Tips</th><th>Supervisor $</th><th>Cashier $</th><th>Card Type</th><th>Room</th><th>Supervisor</th><th>Time Closed</th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="paper-total-row"><th>Total</th><td class="blocked-cell"></td><td>${money(totals.tip)}</td><td>${money(totals.supervisor)}</td><td>${money(totals.cashier)}</td><td class="blocked-cell" colspan="4"></td></tr></tfoot></table></div>`;
}
function cageSmartTabForm(source){
  const tips=Logic.printableTipRows(source.tipRows),totals=Logic.calculateRows(source.tipRows),drawers=[...new Set(tips.map(row=>row.drawer_number).filter(Boolean))].join(", ");
  const rows=paperRows(30,tips,(row)=>`<tr><td>${esc(row?.customer_name||"")}</td><td>${esc(row?.drawer_number||"")}</td><td>${esc(row?.check_number||"")}</td><td>${esc(row?.card_type||"")}</td><td>${esc(row?.time_closed||"")}</td><td class="choice-print">${row?.entry_type==="C"?"✓":""}</td><td class="choice-print">${row?.entry_type==="DD"?"✓":""}</td><td>${paperMoney(row?.tip_cents)}</td></tr>`);
  return `<div class="paper-sheet paper-landscape cage-smarttab-form">${paperBrand()}<header class="cage-form-heading"><h2>CAGE SMARTTAB TIP TOTALS</h2><p>(Cover and Dance Dollar Tips)</p><div class="paper-header-grid">${paperField("Names",(source.workers||[]).join(", "))}${paperField("Tip Pool Day",source.tip_pool_day)}${paperField("Drawer #'s",drawers)}${paperField("Shift",source.shift)}${paperField("Date",source.work_date)}</div></header><table class="paper-table cage-paper-table"><thead><tr><th>Customer Name</th><th>Drawer #</th><th>Check #</th><th>Card Type</th><th>Time Closed</th><th colspan="2">Cover / DD</th><th>Tip $</th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="paper-total-row"><th>Total</th><td colspan="6"></td><td>${money(totals.tip)}</td></tr></tfoot></table></div>`;
}
function chipTotalsForm(source){
  const chips=Logic.printableChipRows(source.chipRows),totals=Logic.calculateChipTotals(source.chipRows);
  const rows=paperRows(25,chips,(row,index)=>`<tr><td>${esc(row?.transfer_to||"")}</td><td>${index+1}</td><td>${esc(row?.tab_number||"")}</td><td>${paperMoney(row?.chipInvoice)}</td><td class="blocked-cell"></td><td></td><td>${paperMoney(row?.grandInvoice)}</td><td>${paperMoney(row?.checkWithoutTip)}</td><td>${paperMoney(row?.tipSmartTab)}</td><td>${paperMoney(row?.totalWithTip)}</td></tr>`);
  const expectedHeader='<span>Xfer to</span><span>#</span><span>Tab #</span><span>Chip Total Invoice</span><span>Chip Total + Chip Fee</span><span>Room Fee Invoice</span><span>Grand Total Invoice</span><span>Check Total Without Tip</span><span>Tip SmartTab</span><span>Total With Tip SmartTab</span>';
  void expectedHeader;
  return `<div class="paper-sheet paper-portrait chip-totals-form">${paperBrand()}<div class="chip-form-meta">${paperField("DATE",source.work_date)}${paperField("TIP DAY(S)",source.tip_pool_day)}${paperField("BANK START / END TIME",`${source.bank_start_time||""} / ${source.bank_end_time||""}`)}${paperField("CASHIER(S)",(source.workers||[]).join(", "))}</div><div class="shift-bands"><span>1PM-3PM</span><span>3PM-END</span><span>START-7AM</span><span>7AM-1PM</span></div><h2>CHIP TOTALS SHEET</h2><p class="selected-shift">Shift: ${esc(source.shift||"")}</p><table class="paper-table chip-totals-paper-table"><thead><tr><th># xfer<br>to</th><th></th><th>TAB #</th><th>Chip Total<br>Invoice</th><th>Chip total<br>+ Chip fee</th><th>Room Fee<br>Invoice</th><th>Grand<br>Total<br>Invoice</th><th>CHECK TOTAL<br>(WITHOUT TIP)</th><th>Tip<br>SmartTab</th><th>Total With Tip<br>SmartTab</th></tr></thead><tbody>${rows}</tbody><tfoot><tr class="paper-total-row"><th colspan="3">TOTAL</th><td>${money(totals.chipInvoice)}</td><td class="blocked-cell"></td><td></td><td>${money(totals.grandInvoice)}</td><td>${money(totals.checkWithoutTip)}</td><td>${money(totals.tipSmartTab)}</td><td>${money(totals.totalWithTip)}</td></tr></tfoot></table><div class="chips-total-label">Total<br>(Chips)</div><div class="checker-box"><em>checker</em><span>${money(totals.chipInvoice)}</span><b>×1.2</b><b>+</b><span></span><b>+</b><span>${money(totals.tipSmartTab)}</span><b>=</b><span>${money(totals.totalWithTip)}</span></div></div>`;
}
function generatedSheetHtml(type,print=false,source=sheetSource()){
  void print;
  if(type==="chip-tips")return clubTipsForm(source);
  if(type==="cage")return cageSmartTabForm(source);
  return chipTotalsForm(source);
}
function renderGeneratedPreview(){
  $("#generatedSheetPreview").innerHTML=generatedSheetHtml(state.currentSheet);
  $$(".generated-card").forEach(card=>card.classList.toggle("selected",card.querySelector("[data-view-sheet]")?.dataset.viewSheet===state.currentSheet));
}
function renderPrint(types,source=sheetSource()){
  $("#printReport").innerHTML=types.map(type=>`<section class="print-sheet ${type}">${generatedSheetHtml(type,true,source)}</section>`).join("");
  if(source===state.shift){state.shift.reportOpenedAt=new Date().toISOString();saveLocal(false);}
  toast("The three populated forms are ready. Choose Save as PDF in the print screen.");
  setTimeout(()=>window.print(),60);
}
function openCompletedShift(id){
  const record=state.archives.find(item=>item.id===id);
  if(!record)return toast("That completed shift could not be found",true);
  state.viewingArchiveId=id;
  state.viewingShift=clone(record.shift);
  Logic.pairShiftFields(state.viewingShift.tipRows,state.viewingShift.chipRows);
  state.currentSheet="chip-tips";
  showPage("sheets");
}
function openCompletedShiftForEdit(id){
  const record=state.archives.find(item=>item.id===id);
  if(!record)return toast("That completed shift could not be found",true);
  clearTimeout(state.saveTimer);
  if(!state.editingArchiveId)state.activeShiftBeforeEdit=state.shift;
  state.shift=clone(record.shift);
  Logic.pairShiftFields(state.shift.tipRows,state.shift.chipRows);
  alignTransactionRows();
  state.editingArchiveId=id;
  state.viewingShift=null;
  state.viewingArchiveId=null;
  showPage("master");
  toast("Editing completed shift. Changes save to the permanent record.");
}
function exitEditMode(){
  if(!state.editingArchiveId)return;
  clearTimeout(state.saveTimer);
  saveLocal(false);
  state.shift=state.activeShiftBeforeEdit||newShift();
  state.activeShiftBeforeEdit=null;
  state.editingArchiveId=null;
  alignTransactionRows();
  renderCompletedShifts();
}
function finishEditingCompletedShift(){
  exitEditMode();
  toast("Finished editing. The completed shift record is updated.");
  showPage("home");
}
function printCompletedShift(id){
  const record=state.archives.find(item=>item.id===id);
  if(!record)return toast("That completed shift could not be found",true);
  const snapshot=clone(record.shift);
  Logic.pairShiftFields(snapshot.tipRows,snapshot.chipRows);
  renderPrint(sheetDefinitions.map(item=>item.id),snapshot);
}
function useActiveShift(){state.viewingShift=null;state.viewingArchiveId=null;renderSheets();}

function hasShiftEntries(source=state.shift){return Logic.printableTipRows(source.tipRows).length>0||Logic.printableChipRows(source.chipRows).length>0;}
function completeShift(){
  clearTimeout(state.saveTimer);
  saveLocal(false);
  if(!hasShiftEntries())return toast("Add at least one transaction before completing this shift",true);
  const completedAt=new Date().toISOString(),archiveId=state.shift.archive_id||uid();
  state.shift.archive_id=archiveId;
  state.shift.completedAt=completedAt;
  state.archives=Logic.upsertCompletedShift(state.archives,state.shift,archiveId,completedAt);
  saveArchives();
  saveLocal(false);
  renderClose();
  renderCompletedShifts();
  toast("Shift saved in Completed Shifts");
}
function startNewShift(){
  const saved=state.shift.archive_id&&state.archives.some(item=>item.id===state.shift.archive_id);
  if(!saved)return toast("Complete and save this shift first",true);
  if(!confirm("Start a new blank shift? The completed shift will stay in Completed Shifts."))return;
  state.shift=newShift();
  state.viewingShift=null;
  state.viewingArchiveId=null;
  localStorage.setItem(SHIFT_KEY,JSON.stringify(state.shift));
  renderHome();
  toast("New shift started. The completed shift is still saved.");
  showPage("master");
}
function renderClose(){
  clearTimeout(state.saveTimer);
  saveLocal(false);
  const tips=Logic.printableTipRows(state.shift.tipRows),chips=Logic.printableChipRows(state.shift.chipRows),shared=Logic.calculateSharedTipTotals(state.shift.tipRows,state.shift.chipRows),chipTotals=Logic.calculateChipTotals(state.shift.chipRows);
  $("#closeTipTotal").textContent=money(shared.tip);
  $("#closeSupervisor").textContent=money(shared.supervisor);
  $("#closeCashier").textContent=money(shared.cashier);
  $("#closeGrandInvoices").textContent=money(chipTotals.finalInvoice);
  const missing=[];
  if(!state.shift.work_date)missing.push("date");
  if(!state.shift.shift)missing.push("shift");
  if(!state.shift.tip_pool_day)missing.push("tip pool day");
  if(!state.shift.workers.length)missing.push("people working");
  const hasEntries=tips.length>0||chips.length>0;
  $("#closeWarnings").innerHTML=!hasEntries?`<div class="notice"><strong>Add at least one transaction before completing this shift.</strong><button class="inline-link-button" data-page="master">Go to shift entry</button></div>`:missing.length?`<div class="notice"><strong>The shift can still be saved.</strong> Missing: ${esc(missing.join(", "))}. The matching fields will remain blank on the sheets. <button class="inline-link-button" data-page="master">Add the missing information</button></div>`:`<div class="success-notice"><strong>All three worksheets are ready.</strong> Complete the shift to keep it in Completed Shifts.</div>`;
  $("#completeShiftButton").disabled=!hasEntries;
  $("#savePdfButton").disabled=!hasEntries;
  const record=state.shift.archive_id&&state.archives.find(item=>item.id===state.shift.archive_id);
  $("#completedConfirmation").hidden=!record;
  $("#completedConfirmation").innerHTML=record?`<strong>Saved in Completed Shifts</strong><p>This shift is permanent and can be reopened from Home. Completing it again updates the same saved record.</p><button class="secondary-button" data-open-completed="${esc(record.id)}">Open saved sheets</button>`:"";
  $("#startNewShiftButton").disabled=!record;
  $("#closeSaveStatus").textContent=record?"Completed shift saved":"Active shift saved";
}

function downloadJson(name,payload){
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),link=document.createElement("a");
  link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const adminCategories=[["employees","People working"],["hosts","Hosts or supervisors"],["locations","Locations or rooms"],["card_types","Card types"],["shifts","Shifts"],["tip_pool_days","Tip pool days"]];
function renderAdmin(){
  $("#adminLists").innerHTML=adminCategories.map(([category,title])=>`<section class="panel admin-list" data-category="${category}"><h2>${title}</h2><form class="list-add"><input maxlength="80" placeholder="Add ${title.toLowerCase()}"><button aria-label="Add">＋</button></form><div class="tag-list">${state.config.options[category].map(item=>`<span class="admin-tag">${esc(item.value)}<button data-delete-option="${item.id}" aria-label="Remove ${esc(item.value)}">Remove</button></span>`).join("")}</div></section>`).join("");
}
function addOption(form){
  const category=form.closest("[data-category]").dataset.category,input=$("input",form),value=Logic.cleanText(input.value,80);
  if(!value)return;
  if(state.config.options[category].some(item=>item.value.toLowerCase()===value.toLowerCase()))return toast("That item already exists",true);
  state.config.options[category].push(option(value));input.value="";saveConfig();renderAdmin();toast("List updated");
}
function deleteOption(id){for(const category of Object.keys(state.config.options))state.config.options[category]=state.config.options[category].filter(item=>item.id!==id);saveConfig();renderAdmin();}
function requestRemoval(kind,id,label){state.pendingRemoval={kind,id};$("#removeDialogText").textContent=`${label} will be permanently erased. Nothing is removed unless you confirm below.`;$("#removeDialog").showModal();}
function cancelRemoval(){state.pendingRemoval=null;$("#removeDialog").close();}
function confirmRemoval(){
  const pending=state.pendingRemoval;
  if(!pending)return cancelRemoval();
  if(pending.kind==="transaction"){
    const index=Number(pending.id);
    if(Number.isInteger(index)&&index>=0){state.shift.tipRows.splice(index,1);state.shift.chipRows.splice(index,1);}
    if(!state.shift.tipRows.length){state.shift.tipRows.push(newTipRow());state.shift.chipRows.push(newChipRow());}
    alignTransactionRows();renderTransactionRows();saveLocal(false);
  }else if(pending.kind==="option")deleteOption(pending.id);
  state.pendingRemoval=null;$("#removeDialog").close();toast("Information removed");
}
function exportSettings(){downloadJson("chip-tips-settings.json",{type:"chip_tips_settings",version:3,config:state.config});}
async function importSettings(file){
  try{
    const data=JSON.parse(await file.text());
    if(data.type!=="chip_tips_settings"||!data.config?.options)throw new Error("Not a Chip Tips settings file");
    if(!confirm("Replace settings on this tablet?"))return;
    state.config=data.config;saveConfig();renderAdmin();toast("Settings imported");
  }catch(error){toast(error.message,true);}
}

function bindEvents(){
  document.addEventListener("click",event=>{
    const page=event.target.closest("[data-page]");if(page)showPage(page.dataset.page);
    const view=event.target.closest("[data-view-sheet]");if(view){state.currentSheet=view.dataset.viewSheet;renderSheets();}
    const print=event.target.closest("[data-print-sheet]");if(print)renderPrint([print.dataset.printSheet]);
    const openCompleted=event.target.closest("[data-open-completed]");if(openCompleted)openCompletedShift(openCompleted.dataset.openCompleted);
    const editCompleted=event.target.closest("[data-edit-completed]");if(editCompleted)openCompletedShiftForEdit(editCompleted.dataset.editCompleted);
    if(event.target.closest("[data-finish-edit]"))finishEditingCompletedShift();
    const printCompleted=event.target.closest("[data-print-completed]");if(printCompleted)printCompletedShift(printCompleted.dataset.printCompleted);
    if(event.target.closest("[data-use-active-shift]"))useActiveShift();
    const transactionRemove=event.target.closest("[data-remove-transaction]");
    if(transactionRemove){const index=Number(transactionRemove.dataset.removeTransaction),tip=state.shift.tipRows[index],chip=state.shift.chipRows[index];requestRemoval("transaction",String(index),`Transaction ${index+1}${tip?.customer_name?` for ${tip.customer_name}`:chip?.tab_number?` for tab ${chip.tab_number}`:""}`);}
    const del=event.target.closest("[data-delete-option]");
    if(del){let label="This administration item";for(const items of Object.values(state.config.options)){const found=items.find(item=>item.id===del.dataset.deleteOption);if(found){label=`Administration item ${found.value}`;break;}}requestRemoval("option",del.dataset.deleteOption,label);}
  });
  $("#transactionRows").addEventListener("input",updateTransactionInput);
  $("#transactionRows").addEventListener("change",updateTransactionInput);
  for(const id of ["workDate","shiftName","tipPoolDay","bankStart","bankEnd"])$("#"+id).addEventListener("change",syncHeader);
  $("#workerChoices").addEventListener("change",syncHeader);
  $("#addTransactionTop").addEventListener("click",addTransaction);
  $("#addTransactionBottom").addEventListener("click",addTransaction);
  $("#masterForm").addEventListener("submit",event=>{event.preventDefault();syncHeader();clearTimeout(state.saveTimer);saveLocal(true);});
  $("#adminLists").addEventListener("submit",event=>{event.preventDefault();addOption(event.target);});
  $("#completeShiftButton").addEventListener("click",completeShift);
  $("#savePdfButton").addEventListener("click",()=>renderPrint(sheetDefinitions.map(item=>item.id),state.shift));
  $("#startNewShiftButton").addEventListener("click",startNewShift);
  $("#cancelRemoveButton").addEventListener("click",cancelRemoval);
  $("#confirmRemoveButton").addEventListener("click",confirmRemoval);
  $("#removeDialog").addEventListener("cancel",event=>{event.preventDefault();cancelRemoval();});
  $("#exportSettingsButton").addEventListener("click",exportSettings);
  $("#importSettingsInput").addEventListener("change",event=>{if(event.target.files[0])importSettings(event.target.files[0]);event.target.value="";});
  $("#installHelp").addEventListener("click",()=>$("#installDialog").showModal());
  $("#installDialog .dialog-close").addEventListener("click",()=>$("#installDialog").close());
  $("#installButton").addEventListener("click",async()=>{if(!state.deferredInstall)return $("#installDialog").showModal();state.deferredInstall.prompt();await state.deferredInstall.userChoice;state.deferredInstall=null;$("#installButton").hidden=true;});
}
function init(){
  loadState();
  $("#heroDate").textContent=new Date().toLocaleDateString([],{weekday:"long",month:"long",day:"numeric"});
  bindEvents();
  renderHome();
  const initial=location.hash.slice(1);
  showPage(["home","master","sheets","close","admin"].includes(initial)?initial:"home");
  if("serviceWorker"in navigator)navigator.serviceWorker.register("sw.js").catch(console.error);
}
window.addEventListener("beforeinstallprompt",event=>{event.preventDefault();state.deferredInstall=event;$("#installButton").hidden=false;});
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="hidden"&&state.shift)saveLocal(false);});
window.addEventListener("beforeunload",()=>{if(state.shift)saveLocal(false);});
document.addEventListener("DOMContentLoaded",init);
