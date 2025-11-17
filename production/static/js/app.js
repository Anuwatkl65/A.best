// ใช้ร่วมทุกหน้า (อ้างอิง id จากเทมเพลตที่แตกไฟล์มาจาก index เดิม) :contentReference[oaicite:3]{index=3}
const API = {
  async call(params){
    const body = new URLSearchParams(params);
    const res = await fetch("/api/", { method:"POST", body });
    const raw = await res.json();
    return (typeof raw.success !== "undefined")
      ? { status: raw.success ? "success":"error", ...raw }
      : raw;
  },
  login: (user, password) => API.call({ action:"login", user, password }),
  getData: () => API.call({ action:"getData" }),
  scan: (lot_no, qty=1, machine_no="MC-01") => API.call({ action:"scan", lot_no, qty, machine_no }),
};

// -------- Login page --------
(function initLogin(){
  const btn = document.getElementById("login-btn");
  if(!btn) return;
  const userEl = document.getElementById("username");
  const passEl = document.getElementById("password");
  const text = document.getElementById("login-btn-text");
  const spin = document.getElementById("login-spinner");
  btn.onclick = async () => {
    btn.disabled = true; text.textContent = "กำลังเข้าสู่ระบบ..."; spin.classList.remove("hidden");
    try {
      const r = await API.login(userEl.value, passEl.value);
      if(r.status !== "success") throw new Error(r.message || "Login failed");
      window.location.href = "/department/";
    } catch(err){ alert(err.message); }
    finally { btn.disabled = false; text.textContent = "เข้าสู่ระบบ"; spin.classList.add("hidden"); }
  };
})();

// -------- Dashboard page (list view แบบย่อ) --------
(function initDashboard(){
  const refreshBtn = document.getElementById("refresh-dashboard-btn");
  if(!refreshBtn) return;
  const filterEl = document.getElementById("filter-input");
  const wrap = document.getElementById("dashboard-content");
  const sumAll = document.getElementById("summary-total");
  const sumPending = document.getElementById("summary-pending");
  const sumIn = document.getElementById("summary-inProgress");
  const sumDone = document.getElementById("summary-completed");
  let data = [];

  function pct(x){ const p = x.target ? Math.min(100, Math.floor((x.scannedCount||0)*100/x.target)) : 0; return p; }
  function renderSummary(){
    const S = {total: data.length, pending:0, inP:0, done:0};
    data.forEach(x=>{ const p=pct(x); if(p===0) S.pending++; else if(p>=100) S.done++; else S.inP++; });
    sumAll.innerHTML = `<div class="text-sm text-gray-500">ทั้งหมด</div><div class="text-2xl font-bold">${S.total}</div>`;
    sumPending.innerHTML = `<div class="text-sm text-gray-500">รอผลิต</div><div class="text-2xl font-bold">${S.pending}</div>`;
    sumIn.innerHTML = `<div class="text-sm text-gray-500">กำลังผลิต</div><div class="text-2xl font-bold">${S.inP}</div>`;
    sumDone.innerHTML = `<div class="text-sm text-gray-500">เสร็จแล้ว</div><div class="text-2xl font-bold">${S.done}</div>`;
  }
  function card(x){
    const p = pct(x);
    const pieces = (x.scannedCount===x.target && x.target>0) ? (x.productionQuantity||0) : ((x.scannedCount||0)*(x.piecesPerBox||0));
    return `
    <div class="rounded-xl bg-gradient-to-r from-purple-600 to-indigo-700 p-0.5 shadow">
      <div class="bg-white p-4 rounded-lg h-full">
        <div class="flex justify-between">
          <div class="pr-2">
            <p class="font-bold text-lg">${x.lotNo||"-"}</p>
            <div class="text-xs text-gray-500 mt-1 space-y-1">
              <p><b>Part :</b> ${x.partNo||"-"}</p>
              <p><b>Customer :</b> ${x.customer||"-"}</p>
              <p><b>Prod Qty :</b> ${(x.productionQuantity||0).toLocaleString()} | <b>Desc :</b> ${x.description||"-"}</p>
              <p><b>Department :</b> ${x.department||"-"} | <b>Machine :</b> ${x.machineNo||"-"}</p>
            </div>
          </div>
          <div class="text-right">
            <span class="text-sm font-mono text-gray-700">${x.scannedCount||0} / ${x.target||0}</span>
            <div class="text-xs mt-1"><span class="font-bold py-0.5 px-2 rounded-md bg-purple-50">${x.type||"-"}</span></div>
          </div>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-5 overflow-hidden my-2">
          <div class="h-5 rounded-full text-white text-xs font-bold flex items-center justify-center"
               style="width:${p}%;background-color:hsl(${(p/100)*120},90%,45%)">${p}%</div>
        </div>
        <div class="flex justify-between text-sm text-gray-700">
          <div>ชิ้น/กล่อง: <b>${(x.piecesPerBox||0).toLocaleString()}</b></div>
          <div>ชิ้นที่ได้: <b>${pieces.toLocaleString()} pcs.</b></div>
        </div>
        <div class="mt-2 text-xs text-gray-400 space-y-1">
          <p><b>สแกนครั้งแรก :</b> ${x.firstScan||"-"}</p>
          <p><b>สแกนล่าสุด :</b> ${x.lastScan||"-"}</p>
        </div>
      </div>
    </div>`;
  }
  function render(){
    const q = (filterEl.value||"").toLowerCase();
    const rows = data.filter(x =>
      !q ||
      (x.lotNo||"").toLowerCase().includes(q) ||
      (x.partNo||"").toLowerCase().includes(q) ||
      (x.customer||"").toLowerCase().includes(q)
    );
    wrap.innerHTML = rows.length ? rows.map(card).join("") :
      `<div class="bg-white p-6 rounded-xl shadow text-center text-gray-500">ไม่พบข้อมูล</div>`;
    renderSummary();
  }
  async function load(){
    const r = await API.getData();
    const rows = (r.data?.dashboardData) || r.data || [];
    data = rows;
    render();
  }
  refreshBtn.onclick = load;
  filterEl && (filterEl.oninput = render);
  load();
})();

// -------- Scan test button --------
(function initScan(){
  const btn = document.getElementById("test-scan-btn");
  if(!btn) return;
  const lbl = document.getElementById("scan-result");
  btn.onclick = async ()=>{
    const lot = prompt("ใส่ LOT:", "LOT-AB-0001");
    if(!lot) return;
    lbl.textContent = `กำลังส่ง: ${lot}`;
    const r = await API.scan(lot, 1, "MC-01");
    lbl.textContent = (r.status==="success") ? `บันทึกสำเร็จ: ${lot}` : `ผิดพลาด: ${r.message||"unknown"}`;
  };
})();


// ===== Context จาก template =====
const ctx = window.__DASHBOARD_CONTEXT__ || { department: "", view_type: "list" };

// ===== Helper: filter ตามแผนก =====
function applyDepartmentFilter(rows){
  const dep = (ctx.department || "").toLowerCase();
  if (!dep || dep === "overall") return rows;
  return rows.filter(r => (r.department || "").toLowerCase() === dep);
}

// ===== Machine View =====
(function initMachineView(){
  if (ctx.view_type !== "machine") return;
  const grid = document.getElementById("machine-grid");
  if (!grid) return;

  function pct(x){ 
    const p = x.target ? Math.min(100, Math.floor((x.scannedCount||0)*100/x.target)) : 0; 
    return p; 
  }

  // สร้าง key เครื่อง -> object รวมข้อมูล
  function groupByMachine(rows){
    const map = {};
    rows.forEach(r=>{
      const m = r.machineNo || "Unknown";
      if(!map[m]) map[m] = {
        machineNo: m,
        lots: [],
        totalTarget: 0,
        totalScanned: 0,
        lastScan: null,
      };
      map[m].lots.push(r);
      map[m].totalTarget += (r.target||0);
      map[m].totalScanned += (r.scannedCount||0);
      const ls = r.lastScan ? new Date(r.lastScan) : null;
      if (ls && (!map[m].lastScan || ls > map[m].lastScan)) map[m].lastScan = ls;
    });
    return Object.values(map).sort((a,b)=> (a.machineNo||"").localeCompare(b.machineNo||""));
  }

  // สถานะเครื่องแบบง่าย: Ready / In Progress / Idle
  function machineStatus(m){
    if(!m.lots.length) return {label:"Ready", color:"bg-emerald-100 text-emerald-700"};
    const now = new Date();
    if (m.lastScan && (now - m.lastScan) <= (2*60*60*1000)) {
      return {label:"In Progress", color:"bg-amber-100 text-amber-700"};
    }
    if (m.totalTarget>0 && m.totalScanned>=m.totalTarget){
      return {label:"Done", color:"bg-sky-100 text-sky-700"};
    }
    return {label:"Ready", color:"bg-emerald-100 text-emerald-700"};
  }

  function card(machine){
    const totalPct = machine.totalTarget>0 ? Math.min(100, Math.floor(machine.totalScanned*100/machine.totalTarget)) : 0;
    const status = machineStatus(machine);
    const topLot = machine.lots[0] || {}; // แสดงตัวอย่าง lot ล่าสุด
    return `
    <div class="rounded-2xl border-2 border-purple-300/60 bg-white shadow-sm p-4">
      <div class="flex justify-between items-start mb-2">
        <div class="flex items-center gap-2">
          <h3 class="text-lg font-extrabold text-gray-800">${machine.machineNo}</h3>
          <button title="ค้นหา" class="text-gray-400 hover:text-gray-600">
            <span class="material-symbols-outlined text-base">search</span>
          </button>
        </div>
        <span class="text-xs px-3 py-1 rounded-full ${status.color} font-semibold">${status.label}</span>
      </div>

      <p class="text-xs text-gray-500 mb-2">
        ${topLot.description ? topLot.description : 'เครื่องกระบุก (ใหม่)'}
      </p>

      <div class="rounded-xl border border-dashed border-gray-200 p-3 mb-3">
        <div class="grid grid-cols-2 gap-y-1 text-sm text-gray-700">
          <div><b>Part:</b> ${topLot.partNo || '-'}</div>
          <div><b>Lot:</b> ${topLot.lotNo || '-'}</div>
          <div><b>Customer:</b> ${topLot.customer || '-'}</div>
          <div><b>Quantity:</b> ${(topLot.scannedCount||0)} / ${(topLot.target||0)}</div>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden mt-2">
          <div class="h-3 rounded-full"
               style="width:${totalPct}%; background-color:hsl(${(totalPct/100)*120},90%,45%)"></div>
        </div>
      </div>

      <div class="text-[12px] text-gray-400">
        <div><b>สแกนครั้งแรก:</b> ${topLot.firstScan || '-'}</div>
        <div><b>สแกนล่าสุด:</b> ${topLot.lastScan || '-'}</div>
      </div>
    </div>`;
  }

(function initMachineView(){
  if (ctx.view_type !== "machine") return;
  const grid = document.getElementById("machine-grid");
  if (!grid) return;

  const elSumAll = document.getElementById("sumAllMachines");
  const elSumReady = document.getElementById("sumReadyMachines");
  const elSumActive = document.getElementById("sumActiveMachines");
  const elSumDone = document.getElementById("sumDoneMachines");

  function pct(x){ 
    return x.target ? Math.min(100, Math.floor((x.scannedCount||0)*100/x.target)) : 0; 
  }

  function groupByMachine(rows){
    const map = {};
    rows.forEach(r=>{
      const m = r.machineNo || "Unknown";
      if(!map[m]) map[m] = {machineNo:m, lots:[], totalTarget:0, totalScanned:0, lastScan:null};
      map[m].lots.push(r);
      map[m].totalTarget += (r.target||0);
      map[m].totalScanned += (r.scannedCount||0);
      const ls = r.lastScan ? new Date(r.lastScan) : null;
      if (ls && (!map[m].lastScan || ls > map[m].lastScan)) map[m].lastScan = ls;
    });
    return Object.values(map);
  }

  function machineStatus(m){
    if(!m.lots.length) return "ready";
    const now = new Date();
    if (m.totalTarget>0 && m.totalScanned>=m.totalTarget) return "done";
    if (m.lastScan && (now - m.lastScan) <= (2*60*60*1000)) return "active";
    return "ready";
  }

  function colorClass(status){
    return {
      ready: "bg-emerald-50 border-emerald-200",
      active: "bg-amber-50 border-amber-300",
      done: "bg-indigo-50 border-indigo-200"
    }[status] || "bg-gray-50 border-gray-200";
  }

  // แผนภาพย่อ (sparkline)
  function sparklineHTML(){
    const bars = Array.from({length:12}).map(()=>{
      const h = Math.random()*40 + 10; // mock data
      return `<rect x="0" width="6" height="${h}" y="${50-h}" rx="2"></rect>`;
    }).join("");
    return `<svg viewBox="0 0 80 50" class="w-full h-10 fill-purple-400">${bars}</svg>`;
  }

  function card(machine){
    const top = machine.lots[0] || {};
    const p = machine.totalTarget>0 ? Math.floor(machine.totalScanned*100/machine.totalTarget) : 0;
    const status = machineStatus(machine);
    return `
      <div class="p-4 rounded-xl border ${colorClass(status)} shadow-sm hover:shadow-md transition">
        <div class="flex justify-between items-start mb-1">
          <h3 class="font-bold text-lg">${machine.machineNo}</h3>
          <span class="text-xs px-2 py-0.5 rounded-full font-semibold ${
            status==='active'?'bg-amber-100 text-amber-700':
            status==='done'?'bg-indigo-100 text-indigo-700':
            'bg-emerald-100 text-emerald-700'
          }">${status.toUpperCase()}</span>
        </div>
        <p class="text-xs text-gray-500 mb-2">${top.description || '-'}</p>
        <div class="w-full bg-gray-200 rounded-full h-2 mb-2">
          <div class="h-2 rounded-full" style="width:${p}%;background-color:hsl(${(p/100)*120},90%,45%)"></div>
        </div>
        <div class="text-[12px] text-gray-600 space-y-0.5 mb-1">
          <div><b>Part:</b> ${top.partNo || '-'}</div>
          <div><b>Lot:</b> ${top.lotNo || '-'}</div>
          <div><b>Qty:</b> ${(top.scannedCount||0)} / ${(top.target||0)}</div>
        </div>
        ${sparklineHTML()}
      </div>
    `;
  }

  async function load(){
    grid.innerHTML = `<div class="text-center text-gray-500">Loading...</div>`;
    const r = await API.getData();
    const rowsRaw = (r.data?.dashboardData) || r.data || [];
    const rows = applyDepartmentFilter(rowsRaw);
    const machines = groupByMachine(rows);

    // update summary
    elSumAll.textContent = machines.length;
    const counts = {ready:0,active:0,done:0};
    machines.forEach(m => counts[machineStatus(m)]++);
    elSumReady.textContent = counts.ready;
    elSumActive.textContent = counts.active;
    elSumDone.textContent = counts.done;

    grid.innerHTML = machines.map(card).join("");
  }

  load();
})();

grid.querySelectorAll(".machine-detail-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const machineNo = btn.dataset.machine;
    const ok = confirm(`ต้องการดูรายละเอียดของเครื่อง ${machineNo} ใช่หรือไม่?`);
    if (!ok) return;

    // /machine/MACHINE_PLACEHOLDER/ -> /machine/M311/
    const baseUrl = MACHINE_DETAIL_URL_TEMPLATE.replace("MACHINE_PLACEHOLDER", machineNo);
    const url = `${baseUrl}?department=${encodeURIComponent(CURRENT_DEPARTMENT)}`;
    window.location.href = url;
  });
});

  function openMachineDetailConfirm(machineNo) {
    if (!machineNo) {
      alert("ไม่พบหมายเลขเครื่องของ Lot นี้");
      return;
    }
    const ok = confirm(`ต้องการดูรายละเอียดงานของเครื่อง ${machineNo} ใช่หรือไม่?`);
    if (ok) {
      // ใช้ department ปัจจุบันจาก context
      const dept = "{{ department }}";
      window.location.href = `/dashboard/machine/${machineNo}/?department=${dept}`;
    }
  }



  async function load(){
    grid.innerHTML = `<div class="text-center text-gray-500">กำลังโหลดข้อมูล...</div>`;
    const r = await API.getData();
    const rowsRaw = (r.data?.dashboardData) || r.data || [];
    const rows = applyDepartmentFilter(rowsRaw);
    const machines = groupByMachine(rows);
    grid.innerHTML = machines.length ? machines.map(card).join("") 
      : `<div class="text-center text-gray-500 bg-white rounded-xl p-6 shadow">ไม่พบข้อมูลเครื่อง</div>`;
  }

  load();
})();
