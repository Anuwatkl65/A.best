// ========================
// API helper (เรียก /api/)
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

  getData() {
    return API.call({ action: "getData" });
  },

  scan(lot_no, qty = 1, machine_no = "MC-01") {
    return API.call({ action: "scan", lot_no, qty, machine_no });
  },
};

// ========================
// Login (ไม่ใช้ API login แล้ว แต่เผื่อไว้)
// ========================
(function initLogin() {
  const btn = document.getElementById("login-btn");
  if (!btn) return;

  const form = btn.closest("form");
  if (!form) return;

  btn.addEventListener("click", () => form.submit());
})();

// ========================
// ปุ่มทดสอบ Scan
// ========================
(function initScan() {
  const btn = document.getElementById("test-scan-btn");
  if (!btn) return;

  const lbl = document.getElementById("scan-result");

  btn.addEventListener("click", async () => {
    const lot = prompt("ใส่ LOT:", "LOT-AB-0001");
    if (!lot) return;

    if (lbl) lbl.textContent = `กำลังส่ง: ${lot}`;

    try {
      const r = await API.scan(lot, 1, "MC-01");

      if (lbl)
        lbl.textContent =
          r.status === "success"
            ? `บันทึกสำเร็จ: ${lot}`
            : `ผิดพลาด: ${r.message || "unknown error"}`;
    } catch (err) {
      if (lbl) lbl.textContent = `ผิดพลาด: ${err.message}`;
    }
  });
})();

// ========================
// Global Context (จาก template)
// ========================
const ctx = window.__DASHBOARD_CONTEXT__ || {
  department: "",
  view_type: "",
};

// ========================
// Helper filter ตามแผนก (ถ้า page อื่นเรียกใช้)
// ========================
function applyDepartmentFilter(rows) {
  const dep = (ctx.department || "").toLowerCase();
  if (!dep || dep === "overall") return rows;
  return rows.filter((r) =>
    (r.department || "").toLowerCase().includes(dep)
  );
}

// ================================
// Machine View: mini charts + auto refresh + search
// ================================
document.addEventListener("DOMContentLoaded", function () {
  // ใช้เฉพาะหน้า Machine View ที่มี Chart.js เท่านั้น
  if (typeof Chart === "undefined") return;

  const cards = document.querySelectorAll(".machine-card");
  if (!cards.length) return; // ถ้าไม่มีการ์ด แสดงว่าไม่ใช่หน้า machine view

  const elSumReady  = document.getElementById("sumReadyMachines");
  const elSumActive = document.getElementById("sumActiveMachines");
  const elSumDone   = document.getElementById("sumDoneMachines");

  const chartMap = new Map(); // เก็บ instance ของแต่ละ mini chart

  // แปลง status -> class สีของ badge
  function statusClass(status) {
    const s = (status || "").toLowerCase();
    if (s === "running" || s === "active") {
      return "bg-amber-100 text-amber-800";
    }
    if (s === "finished" || s === "done") {
      return "bg-indigo-100 text-indigo-800";
    }
    return "bg-emerald-100 text-emerald-800"; // ready / อื่น ๆ
  }

  // สร้าง/อัปเดต mini chart ของการ์ด
  function updateCardChart(card, labels, daily) {
    const canvas = card.querySelector("canvas.machine-mini-chart");
    if (!canvas) return;

    const ctx2d = canvas.getContext("2d");
    const key = card.dataset.machineNo || canvas;

    if (chartMap.has(key)) {
      const ch = chartMap.get(key);
      ch.data.labels = labels;
      ch.data.datasets[0].data = daily;
      ch.update();
    } else {
      const ch = new Chart(ctx2d, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            {
              data: daily,
              backgroundColor: "rgba(129, 140, 248, 0.85)",
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              enabled: true,
              callbacks: {
                label: function (ctx) {
                  const raw = ctx.raw;
                  const formatted =
                    raw && raw.toLocaleString ? raw.toLocaleString() : raw;
                  return formatted + " pcs";
                },
              },
            },
          },
          scales: {
            x: { display: false },
            y: { display: false },
          },
          layout: { padding: 0 },
        },
      });
      chartMap.set(key, ch);
    }
  }

  // นับ Ready / Running / Finished จาก badge
  function updateStatusSummary() {
    let ready = 0;
    let active = 0;
    let done = 0;

    cards.forEach((card) => {
      const badge =
        card.querySelector(".js-status-badge") ||
        card.querySelector(".status-badge");
      const text = (badge?.textContent || "").trim().toLowerCase();

      if (!text || text === "ready") {
        ready++;
      } else if (text === "running" || text === "active") {
        active++;
      } else if (text === "finished" || text === "done") {
        done++;
      }
    });

    if (elSumReady)  elSumReady.textContent  = ready.toString();
    if (elSumActive) elSumActive.textContent = active.toString();
    if (elSumDone)   elSumDone.textContent   = done.toString();
  }

  // ดึง JSON ของการ์ดแต่ละใบ
  async function refreshCard(card) {
    const url = card.dataset.miniChartUrl || card.dataset.summaryUrl;
    if (!url) return;

    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return;

      const data = await res.json();

      const lotNoEl    = card.querySelector(".js-lot-no");
      const partNoEl   = card.querySelector(".js-part-no");
      const custEl     = card.querySelector(".js-customer");
      const targetEl   = card.querySelector(".js-target");
      const prodEl     = card.querySelector(".js-produced");
      const lastScanEl = card.querySelector(".js-last-scan");
      const badgeEl =
        card.querySelector(".js-status-badge") ||
        card.querySelector(".status-badge");

      if (lotNoEl && data.lot_no !== undefined) {
        lotNoEl.textContent = data.lot_no || "-";
      }
      if (partNoEl && data.part_no !== undefined) {
        partNoEl.textContent = data.part_no || "-";
      }
      if (custEl && data.customer !== undefined) {
        custEl.textContent = data.customer || "-";
        custEl.title = data.customer || "";
      }
      if (targetEl && data.target !== undefined) {
        targetEl.textContent =
          data.target && data.target.toLocaleString
            ? data.target.toLocaleString()
            : data.target;
      }
      if (prodEl && data.produced !== undefined) {
        prodEl.textContent =
          data.produced && data.produced.toLocaleString
            ? data.produced.toLocaleString()
            : data.produced;
      }
      if (lastScanEl && data.last_scan_display !== undefined) {
        lastScanEl.textContent = data.last_scan_display || "-";
      }
      if (badgeEl && data.status !== undefined) {
        badgeEl.textContent = data.status || "Ready";
        // เคลียร์ class สีเก่า แล้วใส่สีใหม่
        badgeEl.className =
          (badgeEl.className
            .split(" ")
            .filter((c) => !c.startsWith("bg-") && !c.startsWith("text-"))
            .join(" ") +
            " " +
            statusClass(data.status)
          ).trim();
      }

      const labels = data.labels || [];
      const daily  = data.daily  || [];
      if (labels.length && daily.length) {
        updateCardChart(card, labels, daily);
      }
    } catch (err) {
      console.error("refreshCard error:", err);
    }
  }

  // refresh รอบแรกทุกการ์ด
  cards.forEach((card) => refreshCard(card));
  setTimeout(updateStatusSummary, 1000);

  // refresh ซ้ำทุก 30s
  const REFRESH_EVERY_MS = 30 * 1000;
  setInterval(() => {
    cards.forEach((card) => refreshCard(card));
    updateStatusSummary();
  }, REFRESH_EVERY_MS);

  // Search ตาม machine no
  const searchInput = document.getElementById("machine-search");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      const kw = this.value.trim().toLowerCase();

      cards.forEach((card) => {
        const machineNo = (card.dataset.machineNo || "").toLowerCase();
        const wrapper   = card.closest("a") || card;
        const match     = !kw || machineNo.includes(kw);
        wrapper.style.display = match ? "" : "none";
      });
    });
  }
});

// ========================
// เปิดหน้า Machine Detail (ถ้าต้องเรียก popup ยืนยัน)
// ========================
function openMachineDetailConfirm(machineNo, department) {
  if (!machineNo) return alert("ไม่พบหมายเลขเครื่อง");

  const dept = department || (ctx && ctx.department) || "Overall";
  const ok = confirm(`ต้องการดูงานของเครื่อง ${machineNo} ?`);
  if (!ok) return;

  window.location.href =
    `/dashboard/?department=${encodeURIComponent(
      dept
    )}&view=list&machine_no=${encodeURIComponent(machineNo)}`;
}

// ========================
// Machine Detail – Scan Logs Today
// ========================
async function loadScanLogsToday(machineNo) {
  const res = await fetch(`/api/machine/${machineNo}/scan_logs_today/`);
  const data = await res.json();

  const tbody = document.getElementById("scan-log-table");
  const totalBox = document.getElementById("scan-total");

  tbody.innerHTML = "";

  if (!data.logs.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-gray-400 p-4">
          ไม่พบการสแกนในช่วงเวลานี้
        </td>
      </tr>
    `;
    totalBox.textContent = "0";
    return;
  }

  data.logs.forEach(row => {
    tbody.innerHTML += `
      <tr class="border-b hover:bg-gray-50">
        <td class="p-2">${row.time}</td>
        <td class="p-2">${row.lot_no}</td>
        <td class="p-2">${row.part_no}</td>
        <td class="p-2">${row.customer}</td>
        <td class="p-2 text-right">${row.qty}</td>
      </tr>
    `;
  });

  totalBox.textContent = data.total.toLocaleString();
}

// เรียกครั้งแรก (ใช้ในหน้า machine_detail.html)
if (typeof machineNo !== "undefined") {
  loadScanLogsToday(machineNo);

  // อัปเดตทุก 10 วินาที
  setInterval(() => loadScanLogsToday(machineNo), 10000);
}
