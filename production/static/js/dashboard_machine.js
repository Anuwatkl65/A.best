// ========================
// API helper
// ========================
const API = {
  async call(params) {
    const body = new URLSearchParams(params);
    const res = await fetch("/api/", { method: "POST", body });
    const raw = await res.json();
    return typeof raw.success !== "undefined"
      ? { status: raw.success ? "success" : "error", ...raw }
      : raw;
  },

  getData() { return API.call({ action: "getData" }); },
  scan(lot_no, qty = 1, machine_no = "MC-01") {
    return API.call({ action: "scan", lot_no, qty, machine_no });
  },
};

// ========================
// GLOBAL CONTEXT
// ========================
const ctx = window.__DASHBOARD_CONTEXT__ || {
  department: "",
  view_type: "",
};

// ========================
// MACHINE VIEW – ตัวแปรหลัก
// ========================
const cards = document.querySelectorAll(".js-machine-card");
const elSumReady = document.getElementById("sum-ready");
const elSumActive = document.getElementById("sum-running");
const elSumDone = document.getElementById("sum-finished");

// สีของสถานะ
function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "running" || s === "active") return "bg-amber-100 text-amber-700";
  if (s === "finished" || s === "done") return "bg-indigo-100 text-indigo-700";
  return "bg-emerald-100 text-emerald-700";
}

// อัปเดตกราฟมินิการ์ด
function updateCardChart(card, labels, daily) {
  const canvas = card.querySelector("canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  if (canvas._chart) canvas._chart.destroy();

  canvas._chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: daily,
        backgroundColor: "rgba(129,140,248,0.9)",
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  });
}

// ========================
// STATUS SUMMARY
// ========================
function updateStatusSummary() {
  let ready = 0;
  let active = 0;
  let done = 0;

  cards.forEach(card => {
    const badge = card.querySelector(".js-status-badge");
    const text = (badge?.textContent || "").trim().toLowerCase();

    if (!text || text === "ready") ready++;
    else if (text === "running" || text === "active") active++;
    else if (text === "finished" || text === "done") done++;
  });

  if (elSumReady) elSumReady.textContent = ready;
  if (elSumActive) elSumActive.textContent = active;
  if (elSumDone) elSumDone.textContent = done;
}

// ========================
// REFRESH การ์ดแต่ละใบ
// ========================
async function refreshCard(card) {
  const url = card.dataset.summaryUrl;
  if (!url) return;

  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return;

    const data = await res.json();

    card.querySelector(".js-lot-no").textContent = data.lot_no || "-";
    card.querySelector(".js-part-no").textContent = data.part_no || "-";
    card.querySelector(".js-customer").textContent = data.customer || "-";
    card.querySelector(".js-target").textContent =
      data.target?.toLocaleString() || "-";
    card.querySelector(".js-produced").textContent =
      data.produced?.toLocaleString() || "-";
    card.querySelector(".js-last-scan").textContent = data.last_scan_display || "-";

    const badge = card.querySelector(".js-status-badge");
    badge.textContent = data.status || "Ready";
    badge.className =
      "js-status-badge inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold " +
      statusClass(data.status);

    if (data.labels?.length) updateCardChart(card, data.labels, data.daily);
  } catch (err) {
    console.error("refreshCard:", err);
  }
}

// โหลดครั้งแรก
cards.forEach(card => refreshCard(card));
setTimeout(updateStatusSummary, 800);

// Auto refresh ทุก 30s
setInterval(() => {
  cards.forEach(card => refreshCard(card));
  updateStatusSummary();
}, 30000);

// ========================
// SEARCH เครื่อง
// ========================
const searchInput = document.getElementById("machine-search");

if (searchInput) {
  searchInput.addEventListener("input", function () {
    const kw = this.value.trim().toLowerCase();
    cards.forEach(card => {
      const wrap = card.closest("a") || card;
      const machineNo = (card.dataset.machineNo || "").toLowerCase();
      wrap.style.display = !kw || machineNo.includes(kw) ? "" : "none";
    });
  });
}

// ========================
// MACHINE DETAIL – LOG TODAY
// ========================
async function loadScanLogsToday(machineNo) {
  const res = await fetch(`/api/machine/${machineNo}/scan_logs_today/`);
  const data = await res.json();

  const tbody = document.getElementById("scan-log-table");
  const totalBox = document.getElementById("scan-total");

  tbody.innerHTML = "";

  if (!data.logs.length) {
    tbody.innerHTML = `
      <tr><td colspan="5" class="text-center text-gray-400 p-4">
        ไม่พบการสแกนในช่วงเวลานี้
      </td></tr>`;
    totalBox.textContent = "0";
    return;
  }

  data.logs.forEach(row => {
    tbody.innerHTML += `
      <tr class="hover:bg-gray-50">
        <td>${row.time}</td>
        <td>${row.lot_no}</td>
        <td>${row.part_no}</td>
        <td>${row.customer}</td>
        <td class="text-right">${row.qty}</td>
      </tr>`;
  });

  totalBox.textContent = data.total.toLocaleString();
}

if (typeof machineNo !== "undefined") {
  loadScanLogsToday(machineNo);
  setInterval(() => loadScanLogsToday(machineNo), 10000);
}
