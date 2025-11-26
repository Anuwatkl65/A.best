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
// Login (ไม่ใช้ API login แล้ว)
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
// Filter ตามแผนก
// ========================
function applyDepartmentFilter(rows) {
  const dep = (ctx.department || "").toLowerCase();
  if (!dep || dep === "overall") return rows;
  return rows.filter((r) =>
    (r.department || "").toLowerCase().includes(dep)
  );
}

// ========================
// Dashboard: Machine View
// ========================
(function initMachineView() {
  const grid = document.getElementById("machine-grid");
  if (!grid) return;

  if (ctx.view_type && ctx.view_type !== "machine") return;

  const elSumAll = document.getElementById("sumAllMachines");
  const elSumReady = document.getElementById("sumReadyMachines");
  const elSumActive = document.getElementById("sumActiveMachines");
  const elSumDone = document.getElementById("sumDoneMachines");

  function pctLot(row) {
    const target = row.target || 0;
    const scanned = row.scannedCount || 0;
    return target ? Math.min(100, Math.floor((scanned * 100) / target)) : 0;
  }

  function groupByMachine(rows) {
    const map = {};
    rows.forEach((r) => {
      const m = r.machineNo || "ไม่ระบุเครื่อง";
      if (!map[m]) {
        map[m] = {
          machineNo: m,
          lots: [],
          totalTarget: 0,
          totalScanned: 0,
          lastScan: null,
        };
      }

      map[m].lots.push(r);
      map[m].totalTarget += r.target || 0;
      map[m].totalScanned += r.scannedCount || 0;

      if (r.lastScan) {
        const ls = new Date(r.lastScan);
        if (!map[m].lastScan || ls > map[m].lastScan) map[m].lastScan = ls;
      }
    });

    return Object.values(map).sort((a, b) =>
      (a.machineNo || "").localeCompare(b.machineNo || "")
    );
  }

  function machineStatus(machine) {
    if (!machine.lots.length) return "ready";

    const now = new Date();
    if (machine.totalTarget > 0 && machine.totalScanned >= machine.totalTarget)
      return "done";

    if (
      machine.lastScan &&
      now - machine.lastScan <= 2 * 60 * 60 * 1000
    )
      return "active";

    return "ready";
  }

  // ---------- Machine View: mini charts ----------
(function () {
  // ต้องมี Chart.js โหลดมาก่อน (base.html มี <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>)
  if (typeof Chart === "undefined") return;

  const cards = document.querySelectorAll("[data-mini-chart-url]");

  if (!cards.length) return; // ไม่ได้อยู่หน้า Machine View ก็จบ

  cards.forEach((card) => {
    const url = card.dataset.miniChartUrl;
    const canvas = card.querySelector("canvas.machine-mini-chart");
    if (!url || !canvas) return;

    const ctx = canvas.getContext("2d");

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        const labels = data.labels || [];
        const daily = data.daily || [];

        if (!labels.length || !daily.length) {
          // ไม่มีข้อมูล ไม่ต้องวาด
          return;
        }

        // ป้องกันไม่ให้ chart ซ้อนกัน ถ้า reload JS ซ้ำ
        if (canvas._miniChartInstance) {
          canvas._miniChartInstance.destroy();
        }

        const chart = new Chart(ctx, {
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
              x: {
                display: false,
              },
              y: {
                display: false,
              },
            },
            layout: {
              padding: 0,
            },
          },
        });

        canvas._miniChartInstance = chart;
      })
      .catch((err) => {
        console.error("Error loading mini chart:", err);
      });
  });
})();


  function badge(status) {
    return {
      active: "bg-amber-100 text-amber-700",
      done: "bg-indigo-100 text-indigo-700",
      ready: "bg-emerald-100 text-emerald-700",
    }[status];
  }

  function cardColor(status) {
    return {
      active: "border-amber-200 bg-amber-50/40",
      done: "border-indigo-200 bg-indigo-50/40",
      ready: "border-emerald-200 bg-emerald-50/40",
    }[status];
  }

  function machineCard(machine) {
    const status = machineStatus(machine);
    const top = machine.lots[0] || {};
    const totalPct =
      machine.totalTarget > 0
        ? Math.floor((machine.totalScanned * 100) / machine.totalTarget)
        : 0;

    return `
      <div class="p-4 rounded-2xl border ${cardColor(
        status
      )} shadow-sm hover:shadow-md">
        <div class="flex justify-between items-start mb-2">
          <h3 class="text-lg font-bold">${machine.machineNo}</h3>
          <span class="px-2 py-1 text-[10px] rounded-full font-semibold ${badge(
            status
          )}">${status}</span>
        </div>

        <p class="text-xs text-gray-500 mb-2">${top.description || "-"}</p>

        <div class="border border-dashed p-3 rounded-xl bg-white">
          <div class="grid grid-cols-2 text-xs text-gray-600">
            <div><b>Part:</b> ${top.partNo || "-"}</div>
            <div class="text-right"><b>Lot:</b> ${top.lotNo || "-"}</div>
            <div><b>Customer:</b> ${top.customer || "-"}</div>
            <div class="text-right"><b>Qty:</b> ${(top.scannedCount || 0).toLocaleString()} / ${(top.target || 0).toLocaleString()}</div>
          </div>

          <div class="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div class="h-2 rounded-full"
                 style="width:${totalPct}%; background-color:hsl(${
      (totalPct / 100) * 120
    },90%,45%)"></div>
          </div>
        </div>

        <div class="flex justify-between text-[11px] text-gray-600 mt-2">
          <div>
            <div><b>รวมเป้า:</b> ${machine.totalTarget.toLocaleString()}</div>
            <div><b>สแกนแล้ว:</b> ${machine.totalScanned.toLocaleString()}</div>
          </div>
          <div class="text-right">
            <div><b>สแกนล่าสุด:</b></div>
            <div>${machine.lastScan?.toLocaleString() || "-"}</div>
          </div>
        </div>
      </div>
    `;
  }

  async function load() {
    grid.innerHTML =
      `<div class="text-center p-6 text-gray-500">กำลังโหลด...</div>`;

    try {
      const r = await API.getData();
      const rows = applyDepartmentFilter(r.data?.dashboardData || r.data || []);
      const machines = groupByMachine(rows);

      if (elSumAll) elSumAll.textContent = machines.length;

      if (elSumReady || elSumActive || elSumDone) {
        const sum = { ready: 0, active: 0, done: 0 };
        machines.forEach((m) => sum[machineStatus(m)]++);
        if (elSumReady) elSumReady.textContent = sum.ready;
        if (elSumActive) elSumActive.textContent = sum.active;
        if (elSumDone) elSumDone.textContent = sum.done;
      }

      grid.innerHTML = machines
        .map((m) => machineCard(m))
        .join("");
    } catch (err) {
      grid.innerHTML =
        `<div class="text-center text-red-500 p-6 bg-white rounded-xl">โหลดข้อมูลไม่สำเร็จ</div>`;
    }
  }

  load();
})();

// ========================
// เปิดหน้า Machine Detail
// ========================
function openMachineDetailConfirm(machineNo, department) {
  if (!machineNo) return alert("ไม่พบหมายเลขเครื่อง");

  const dept = department || ctx.department || "Overall";
  const ok = confirm(`ต้องการดูงานของเครื่อง ${machineNo} ?`);
  if (!ok) return;

  window.location.href =
    `/dashboard/machine/${machineNo}/?department=${dept}`;
}

