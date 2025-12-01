    // ========================
    // API helper (เดิม ใช้กับปุ่ม test-scan ได้)
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
    // ปุ่มทดสอบ Scan (ของเดิม ถ้ามีในหน้าไหนก็ยังใช้ได้)
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
    // Global Context (เผื่อใช้ทีหลัง)
    // ========================
    const ctx = window.__DASHBOARD_CONTEXT__ || {
    department: "",
    view_type: "",
    };

    // ========================
    // Machine View: mini charts + auto refresh + search
    // ========================
    document.addEventListener("DOMContentLoaded", function () {
    // ต้องมี Chart.js โหลดมาก่อน
    if (typeof Chart === "undefined") {
        return;
    }

    const cards = document.querySelectorAll(".machine-card");
    if (!cards.length) return; // ไม่ใช่หน้า Machine View

    const elSumReady = document.getElementById("sumReadyMachines");
    const elSumActive = document.getElementById("sumActiveMachines");
    const elSumDone = document.getElementById("sumDoneMachines");

    // เก็บ chart instance ของแต่ละการ์ดไว้ใน element เอง
    const chartMap = new Map();

    // แปลงสถานะ text -> class สี
    function statusClass(status) {
        const s = (status || "").toLowerCase();
        if (s === "running" || s === "active") {
        return "bg-amber-100 text-amber-800";
        }
        if (s === "finished" || s === "done") {
        return "bg-indigo-100 text-indigo-800";
        }
        return "bg-emerald-100 text-emerald-800";
    }

    // สร้าง/อัปเดตกราฟของการ์ด
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

    // อัปเดตสรุป Ready / Running / Finished
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

        if (elSumReady) elSumReady.textContent = ready;
        if (elSumActive) elSumActive.textContent = active;
        if (elSumDone) elSumDone.textContent = done;
    }

    // ดึงข้อมูลการ์ดจาก API แล้วอัปเดต DOM + chart
    async function refreshCard(card) {
        // รองรับทั้ง data-mini-chart-url (ของ template ล่าสุด) และ data-summary-url (เผื่อของเก่า)
        const url = card.dataset.miniChartUrl || card.dataset.summaryUrl;
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
            badgeEl.className =
            (badgeEl.className
                .split(" ")
                .filter((c) => !c.startsWith("bg-") && !c.startsWith("text-"))
                .join(" ") +
                " " +
                statusClass(data.status)).trim();
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

    // refresh การ์ดทั้งหมดครั้งแรก
    cards.forEach((card) => refreshCard(card));
    // หลังจากอัปเดตครั้งแรกแล้ว คำนวณ summary
    setTimeout(updateStatusSummary, 1000);

    // ตั้ง interval ให้รีเฟรชการ์ดทุก X วินาที
    const REFRESH_EVERY_MS = 30 * 1000; // 30 วินาที
    setInterval(() => {
        cards.forEach((card) => refreshCard(card));
    }, REFRESH_EVERY_MS);

    // --------------------
    // Search: filter การ์ดตาม machine no หรือ text ภายใน
    // --------------------
    const searchInput = document.getElementById("machine-search");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
        const kw = this.value.trim().toLowerCase();

        cards.forEach((card) => {
            const machineNo = (card.dataset.machineNo || "").toLowerCase();
            const textAll = card.innerText.toLowerCase();
            const match =
            !kw || machineNo.includes(kw) || textAll.includes(kw);

            // template ล่าสุด การ์ดเป็น <div class="machine-card"> ตรง ๆ
            // ถ้าอนาคตห่อด้วย <a> ก็ให้เลือก parent ที่เป็น a ถ้ามี
            const wrapper = card.closest("a") || card;
            wrapper.style.display = match ? "" : "none";
        });
        });
    }
    });

    // ========================
    // ฟังก์ชันเปิด Machine Detail (ถ้าหน้าอื่นเรียกใช้)
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
