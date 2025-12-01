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

// ========================
// Machine View: mini charts + auto refresh + search
// ========================
document.addEventListener("DOMContentLoaded", function () {
  // ต้องมี Chart.js โหลดมาก่อน
  if (typeof Chart === "undefined") {
    return;
  }

  // การ์ดเครื่องในหน้า Machine View
  const cards = document.querySelectorAll(".machine-card");
  if (!cards.length) return; // ไม่ใช่หน้า Machine View

  // summary กล่องเล็ก ๆ ด้านขวา
  const elSumAll = document.getElementById("sumAllMachines");
  const elSumReady = document.getElementById("sumReadyMachines");
  const elSumActive = document.getElementById("sumActiveMachines");
  const elSumDone = document.getElementById("sumDoneMachines");

  if (elSumAll) elSumAll.textContent = cards.length.toString();

  // เก็บ chart instance ต่อเครื่อง
  const chartMap = new Map();

  // map สถานะ -> class ตราบนการ์ด
  function statusClass(status) {
    const s = (status || "").toLowerCase();
    if (s === "running" || s === "active") {
      return "bg-amber-100 text-amber-800";
    }
    if (s === "finished" || s === "done") {
      return "bg-indigo-100 text-indigo-800";
    }
    return "bg-emerald-100 text-emerald-800"; // ready
  }

  // สร้างหรืออัปเดต chart ของการ์ดหนึ่งใบ
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
              backgroundColor: "rgba(129, 140, 248, 0.85)", // ม่วง
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
                label: function (c) {
                  const raw = c.raw;
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

  // นับ Ready / Running / Finished จาก badge บนการ์ด
  function updateStatusSummary() {
    let ready = 0;
    let active = 0;
    let done = 0;

    cards.forEach((card) => {
      const badge = card.querySelector(".js-status-badge");
      const text = (badge?.textContent || "").trim().toLowerCase();

      if (!text || text === "ready") {
        ready++;
      } else if (text === "running" || text === "active") {
        active++;
      } else if (text === "finished" || text === "done") {
        done++;
      }
    });

    if (elSumReady) elSumReady.textContent = ready.toString();
    if (elSumActive) elSumActive.textContent = active.toString();
    if (elSumDone) elSumDone.textContent = done.toString();
  }

  // ดึงข้อมูล JSON ของการ์ดและอัปเดต DOM + กราฟ
  async function refreshCard(card) {
    const url = card.dataset.summaryUrl;
    if (!url) return;

    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return;

      const data = await res.json();

      const lotNoEl = card.querySelector(".js-lot-no");
      const partNoEl = card.querySelector(".js-part-no");
      const custEl = card.querySelector(".js-customer");
      const targetEl = card.querySelector(".js-target");
      const prodEl = card.querySelector(".js-produced");
      const lastScanEl = card.querySelector(".js-last-scan");
      const badgeEl = card.querySelector(".js-status-badge");

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
        badgeEl.className =
          "js-status-badge inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold " +
          statusClass(data.status);
      }

      const labels = data.labels || [];
      const daily = data.daily || [];
      if (labels.length && daily.length) {
        updateCardChart(card, labels, daily);
      }
    } catch (err) {
      console.error("refreshCard error:", err);
    }
  }

  // refresh การ์ดครั้งแรก
  cards.forEach((card) => refreshCard(card));

  // อัปเดต summary หลังจากดึงข้อมูลรอบแรก
  setTimeout(updateStatusSummary, 1000);

  // auto refresh ทุก 30 วินาที
  const REFRESH_EVERY_MS = 30 * 1000;
  setInterval(() => {
    cards.forEach((card) => refreshCard(card));
    updateStatusSummary();
  }, REFRESH_EVERY_MS);

  // --------------------
  // Search: filter การ์ดตามหมายเลขเครื่อง / ข้อความ
  // --------------------
  const searchInput = document.getElementById("machine-search");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      const kw = this.value.trim().toLowerCase();

      cards.forEach((card) => {
        const wrapper = card.closest("a") || card; // เผื่อมี <a> ครอบ
        const machineNo = (card.dataset.machineNo || "").toLowerCase();
        const textAll = card.innerText.toLowerCase();

        const match =
          !kw || machineNo.includes(kw) || textAll.includes(kw);

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
