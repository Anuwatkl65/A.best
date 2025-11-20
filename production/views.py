from datetime import datetime
import json
import openpyxl

from django.db.models import Sum, Q
from django.db.models.functions import TruncDate, Coalesce
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from openpyxl.utils import get_column_letter
from django.http import HttpResponse

from .models import Lot, ScanRecord, UserProfile


# label ชื่อแผนก
LABELS = {"Overall": "ภาพรวม", "Preform": "พรีฟอร์ม"}


# ---------- Helper functions (ORM + shared logic) ----------


def _is_staff_or_admin(user):
    if not user.is_authenticated:
        return False
    up = getattr(user, "userprofile", None)
    return (up and up.role in ["admin", "staff"]) or user.is_staff or user.is_superuser


def _annotate_lots(qs):
    """
    เพิ่มฟิลด์ produced_qty ให้แต่ละ Lot ด้วย ORM
    ใช้ sum ของ ScanRecord.qty เพื่อลด N+1 query
    """
    return qs.annotate(produced_qty=Coalesce(Sum("scans__qty"), 0))


def _build_lot_list(qs):
    """
    รับ queryset ของ Lot (ผ่านการ filter แล้ว) -> คืนค่า:
    - lots: list สำหรับใช้ใน template
    - summary: dict ค่า waiting / in_progress / finished / total_lots
    """
    qs = _annotate_lots(qs)

    lots = []
    waiting = 0
    in_progress = 0
    finished = 0

    for lot in qs.order_by("lot_no"):
        produced = lot.produced_qty or 0
        target = lot.target or lot.production_quantity or 0

        if target > 0:
            progress = min(100, int(produced * 100 / target))
        else:
            progress = 0

        if produced == 0:
            waiting += 1
        elif progress >= 100:
            finished += 1
        else:
            in_progress += 1

        boxes = 0
        if lot.pieces_per_box:
            boxes = int(produced / lot.pieces_per_box)

        lots.append(
            {
                "lot_no": lot.lot_no,
                "part_no": lot.part_no,
                "customer": lot.customer,
                "description": lot.description,
                "department": lot.department,
                "machine_no": lot.machine_no,
                "type": lot.type or "Order",
                "produced": produced,
                "target": target,
                "progress": progress,
                "boxes": boxes,
                "first_scan": lot.first_scan,
                "last_scan": lot.last_scan,
            }
        )

    summary = {
        "total_lots": qs.count(),
        "waiting": waiting,
        "in_progress": in_progress,
        "finished": finished,
    }
    return lots, summary


def _build_type_counts(qs):
    """
    นับจำนวน lot ตาม type ใช้แสดงกล่องด้านบนของ List View
    qs ควรเป็น queryset หลัง filter แผนก / search แต่ก่อน filter status
    """
    return {
        "all": qs.count(),
        "order": qs.filter(type__iexact="Order").count(),
        "sample": qs.filter(type__iexact="Sample").count(),
        "reserved": qs.filter(type__iexact="Reserved").count(),
        "extra": qs.filter(type__iexact="Extra").count(),
        "claim": qs.filter(type__iexact="Claim").count(),
    }


# ---------- Auth ----------


def login_page(request):
    if request.user.is_authenticated:
        return redirect("home_menu")

    if request.method == "POST":
        u = request.POST.get("username", "").strip()
        p = request.POST.get("password", "").strip()
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            return redirect("home_menu")

        return render(
            request,
            "production/login.html",
            {"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
        )

    return render(request, "production/login.html")


def logout_view(request):
    logout(request)
    return redirect("login_page")


# ---------- Pages พื้นฐาน ----------


@login_required
def index(request):
    return render(request, "production/index.html")


@login_required
def department_select(request):
    return render(request, "production/department_select.html")


@login_required
def view_select(request):
    """
    เลือกมุมมองของแต่ละแผนก
    ถ้าเลือก Overall ให้ข้ามไป List View ทันที
    """
    dept = request.GET.get("department", "Overall")

    if dept.lower() == "overall":
        return redirect(f"{reverse('dashboard')}?department=Overall&view=list")

    return render(
        request,
        "production/view_select.html",
        {
            "department": dept,
            "department_label": LABELS.get(dept, dept),
        },
    )


# ---------- Dashboard หลัก (List / Machine / Order / Productivity) ----------


@login_required
def dashboard(request):
    dept = request.GET.get("department", "Overall")
    view_type = request.GET.get("view", "list")  # list / machine / order / productivity
    machine_no_filter = request.GET.get("machine_no", "").strip()
    lot_type = request.GET.get("lot_type", "all")  # ใช้กับปุ่ม filter ด้านบน
    layout = request.GET.get("layout", "card")  # ใช้เปลี่ยน layout (machine)
    status = request.GET.get("status", "all")  # waiting / in_progress / finished

    # normalize layout
    if layout not in ["card", "table"]:
        layout = "card"

    department_label = LABELS.get(dept, dept)

    # ---------- ดึงข้อมูล Lot ----------
    qs = Lot.objects.all()

    # filter ตามแผนก
    if dept == "Preform":
        qs = qs.filter(department__icontains="พรีฟอร์ม")
    elif dept == "Overall":
        # ภาพรวมไม่ filter เพิ่ม
        pass
    else:
        qs = qs.filter(department__icontains=department_label)

    # filter ตามเครื่อง (ถ้ามาจาก machine_detail หรือ query)
    if machine_no_filter:
        qs = qs.filter(machine_no__iexact=machine_no_filter)

    # search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(lot_no__icontains=q)
            | Q(part_no__icontains=q)
            | Q(customer__icontains=q)
        )

    # เก็บ qs เดิมไว้ใช้สรุป count ด้านบน (ไม่โดน filter lot_type / status)
    qs_for_counts = qs

    # ---------- filter ตาม type จากปุ่มด้านบน ----------
    active_type = lot_type
    if lot_type != "all":
        type_map = {
            "order": "Order",
            "sample": "Sample",
            "reserved": "Reserved",
            "extra": "Extra",
            "claim": "Claim",
        }
        t = type_map.get(lot_type.lower())
        if t:
            qs = qs.filter(type__iexact=t)

    # ---------- สร้าง list lots + summary ----------
    lots_all, summary = _build_lot_list(qs)

    # ---------- filter ตามสถานะ (ใช้เฉพาะ List View) ----------
    active_status = (
        status if status in ["all", "waiting", "in_progress", "finished"] else "all"
    )

    if view_type == "list" and active_status != "all":
        if active_status == "waiting":
            lots = [l for l in lots_all if l["produced"] == 0]
        elif active_status == "in_progress":
            lots = [l for l in lots_all if 0 < l["progress"] < 100]
        elif active_status == "finished":
            lots = [l for l in lots_all if l["progress"] >= 100]
        else:
            lots = lots_all
    else:
        lots = lots_all

    # ---------- นับจำนวน lot ตาม type (สำหรับกล่องด้านบน) ----------
    type_counts = _build_type_counts(qs_for_counts)

    # ---------- grouped_lots (ใช้กับ Order View แบบเดิม) ----------
    grouped_lots = {
        "Order": [],
        "Sample": [],
        "Reserved": [],
        "Extra": [],
        "Claim": [],
    }
    for lot in lots:
        t = (lot["type"] or "Order").title()
        if t not in grouped_lots:
            grouped_lots[t] = []
        grouped_lots[t].append(lot)

    # ---------- สรุปยอดรวมแบบ Order Dashboard ----------
    overall_qty_by_type = {
        "Order": (
            qs_for_counts.filter(type__iexact="Order")
            .aggregate(s=Sum("target"))["s"]
            or 0
        ),
        "Sample": (
            qs_for_counts.filter(type__iexact="Sample")
            .aggregate(s=Sum("target"))["s"]
            or 0
        ),
        "Reserved": (
            qs_for_counts.filter(type__iexact="Reserved")
            .aggregate(s=Sum("target"))["s"]
            or 0
        ),
        "Extra": (
            qs_for_counts.filter(type__iexact="Extra")
            .aggregate(s=Sum("target"))["s"]
            or 0
        ),
        "Claim": (
            qs_for_counts.filter(type__iexact="Claim")
            .aggregate(s=Sum("target"))["s"]
            or 0
        ),
    }
    overall_total_target = sum(overall_qty_by_type.values())

    # ---------- Machine summary สำหรับ Order View ----------
    machine_summaries = []
    if view_type == "order":
        machine_map = {}

        for lot in lots:
            machine_name = lot["machine_no"] or "ไม่ระบุเครื่อง"
            ms = machine_map.setdefault(
                machine_name,
                {
                    "machine_no": machine_name,
                    "total_target": 0,
                    "total_produced": 0,
                    "types": {
                        "Order": {"target": 0, "count": 0},
                        "Sample": {"target": 0, "count": 0},
                        "Reserved": {"target": 0, "count": 0},
                        "Extra": {"target": 0, "count": 0},
                        "Claim": {"target": 0, "count": 0},
                    },
                    "lots": [],
                },
            )

            ms["total_target"] += lot["target"]
            ms["total_produced"] += lot["produced"]

            t = (lot["type"] or "Order").title()
            if t not in ms["types"]:
                ms["types"][t] = {"target": 0, "count": 0}
            ms["types"][t]["target"] += lot["target"]
            ms["types"][t]["count"] += 1

            ms["lots"].append(lot)

        for ms in machine_map.values():
            if ms["total_target"] > 0:
                ms["progress"] = int(
                    min(100, ms["total_produced"] * 100 / ms["total_target"])
                )
            else:
                ms["progress"] = 0

            machine_summaries.append(ms)

        machine_summaries.sort(key=lambda x: x["machine_no"])

    # ---------- Machine cards สำหรับ Machine View ----------
    machines = []
    if view_type == "machine":
        machine_map = {}

        # รวม lot ตามหมายเลขเครื่อง
        for lot in lots:
            m = lot["machine_no"] or "-"
            info = machine_map.setdefault(
                m,
                {
                    "machine_no": m,
                    "lots": [],
                    "active_lot": None,
                    "status": "Ready",
                },
            )
            info["lots"].append(lot)

        # หา active lot + สถานะ
        for m, info in machine_map.items():
            running_lot = [
                x for x in info["lots"] if 0 < x["progress"] < 100
            ]
            finished_lot = [x for x in info["lots"] if x["progress"] >= 100]

            if running_lot:
                active = sorted(
                    running_lot,
                    key=lambda x: x["last_scan"]
                    or x["first_scan"]
                    or datetime.min,
                )[-1]
                info["active_lot"] = active
                info["status"] = "Running"
            elif finished_lot:
                active = sorted(
                    finished_lot,
                    key=lambda x: x["last_scan"]
                    or x["first_scan"]
                    or datetime.min,
                )[-1]
                info["active_lot"] = active
                info["status"] = "Finished"
            elif info["lots"]:
                active = sorted(
                    info["lots"],
                    key=lambda x: x["last_scan"]
                    or x["first_scan"]
                    or datetime.min,
                )[-1]
                info["active_lot"] = active
                info["status"] = "Ready"
            else:
                info["active_lot"] = None
                info["status"] = "Ready"

        machines = sorted(
            machine_map.values(),
            key=lambda x: x["machine_no"] or "",
        )

    # ---------- เลือก template ----------
    template_map = {
        "list": "production/dashboard_list.html",
        "machine": "production/dashboard_machine.html",
        "order": "production/dashboard_order.html",
        "productivity": "production/dashboard_productivity.html",
    }
    template_name = template_map.get(view_type, "production/dashboard_list.html")

    context = {
        "department": dept,
        "department_label": department_label,
        "view_type": view_type,
        "type_counts": type_counts,
        "summary": summary,
        "lots": lots,
        "grouped_lots": grouped_lots,
        "search_query": q,
        "from_date": request.GET.get("from", ""),
        "to_date": request.GET.get("to", ""),
        "machine_no": machine_no_filter,
        "active_type": active_type,
        "active_status": active_status,
        "layout": layout,
        # สำหรับ Order View ใหม่
        "overall_qty_by_type": overall_qty_by_type,
        "overall_total_target": overall_total_target,
        "machine_summaries": machine_summaries,
        # สำหรับ Machine View
        "machines": machines,
    }
    return render(request, template_name, context)


# ---------- Machine detail (ใช้ template list เดิม) ----------


@login_required
def machine_detail(request, machine_no):
    dept = request.GET.get("department", "Preform")

    qs = Lot.objects.filter(
        department__icontains="พรีฟอร์ม" if dept == "Preform" else dept,
        machine_no__iexact=machine_no,
    )

    lots, summary = _build_lot_list(qs)
    type_counts = _build_type_counts(qs)

    ctx = {
        "department": dept,
        "department_label": LABELS.get(dept, dept),
        "view_type": "list",
        "machine_no": machine_no,
        "lots": lots,
        "summary": summary,
        "type_counts": type_counts,
        "active_type": "all",
        "active_status": "all",
    }

    return render(request, "production/dashboard_list.html", ctx)


# ---------- Lot detail + Chart ----------


@login_required
def lot_detail(request, lot_no):
    dept = request.GET.get("department", "Overall")
    department_label = LABELS.get(dept, dept)

    lot = get_object_or_404(Lot, lot_no=lot_no)

    produced = lot.scans.aggregate(s=Sum("qty"))["s"] or 0
    target = lot.target or lot.production_quantity or 0
    if target > 0:
        progress = min(100, int(produced * 100 / target))
    else:
        progress = 0

    boxes = 0
    if lot.pieces_per_box:
        boxes = int(produced / lot.pieces_per_box)

    # log การสแกนทั้งหมด (สำหรับตาราง)
    scan_logs = lot.scans.order_by("scanned_at")

    # ---------- เตรียมข้อมูลกราฟ: ยอดสแกนต่อวัน + สะสม ----------
    daily_qs = (
        lot.scans.annotate(d=TruncDate("scanned_at"))
        .values("d")
        .annotate(total_qty=Sum("qty"))
        .order_by("d")
    )

    chart_labels = []
    chart_daily = []
    chart_cumsum = []
    running = 0

    for row in daily_qs:
        d = row["d"]
        qty = row["total_qty"] or 0
        running += qty

        chart_labels.append(d.strftime("%d/%m"))
        chart_daily.append(qty)
        chart_cumsum.append(running)

    ctx = {
        "department": dept,
        "department_label": department_label,
        "lot": lot,
        "produced": produced,
        "target": target,
        "progress": progress,
        "boxes": boxes,
        "scan_logs": scan_logs,
        "chart_labels": json.dumps(chart_labels),
        "chart_daily": json.dumps(chart_daily),
        "chart_cumsum": json.dumps(chart_cumsum),
    }
    return render(request, "production/lot_detail.html", ctx)


# ---------- หน้าประกอบอื่น ๆ ----------


@login_required
def productivity_view(request):
    return render(request, "production/productivity_view.html")


@login_required
def productivity_table(request):
    return render(request, "production/productivity_table.html")


@login_required
def scan(request):
    return render(request, "production/scan.html")


@login_required
def qr_export(request):
    return render(request, "production/qr_export.html")


@login_required
def user_profile(request):
    return render(request, "production/user_profile.html")


@login_required
@user_passes_test(_is_staff_or_admin)
def user_list_admin(request):
    return render(request, "production/user_list_admin.html")


@login_required
@user_passes_test(_is_staff_or_admin)
def data_collect(request):
    return render(request, "production/data_collect.html")


@login_required
@user_passes_test(_is_staff_or_admin)
def user_control(request):
    return render(request, "production/user_control.html")


# ---------- API (mock จากระบบเดิม) ----------


def _mock_if_empty():
    if not Lot.objects.exists():
        lot = Lot.objects.create(
            lot_no="LOT-AB-0001",
            part_no="PN-001",
            customer="A.Best",
            description="Demo lot",
            production_quantity=1000,
            pieces_per_box=50,
            target=1000,
            department="Assembly",
            machine_no="MC-01",
            type="Normal",
            first_scan=now(),
            last_scan=now(),
        )
        ScanRecord.objects.create(lot=lot, machine_no="MC-01", qty=250)
        ScanRecord.objects.create(lot=lot, machine_no="MC-01", qty=300)


@csrf_exempt
def api(request):
    action = request.POST.get("action") or request.GET.get("action")
    if not action:
        return JsonResponse(
            {"status": "error", "message": "Missing action"}, status=400
        )

    # mock login
    if action == "login":
        user = request.POST.get("user") or request.GET.get("user")
        password = request.POST.get("password") or request.GET.get("password")
        ok = (user in ["admin", "staff", "visitor"]) and (password == "1234")
        if ok:
            return JsonResponse(
                {
                    "status": "success",
                    "user": {
                        "name": user.title(),
                        "username": user,
                        "role": user,
                    },
                    "token": "demo-token",
                }
            )
        return JsonResponse(
            {"status": "error", "message": "Invalid credentials"}, status=401
        )

    if action == "getData":
        _mock_if_empty()
        rows = []
        for lot in Lot.objects.all().order_by("lot_no"):
            produced = lot.scans.aggregate(s=Sum("qty"))["s"] or 0
            progress = (
                0
                if not lot.target
                else min(100, int(produced * 100 / lot.target))
            )
            rows.append(
                {
                    "lotNo": lot.lot_no,
                    "partNo": lot.part_no,
                    "customer": lot.customer,
                    "description": lot.description,
                    "productionQuantity": lot.production_quantity,
                    "piecesPerBox": lot.pieces_per_box,
                    "target": lot.target,
                    "department": lot.department,
                    "machineNo": lot.machine_no,
                    "type": lot.type or "Order",
                    "firstScan": lot.first_scan.isoformat()
                    if lot.first_scan
                    else None,
                    "lastScan": lot.last_scan.isoformat()
                    if lot.last_scan
                    else None,
                    "scannedCount": produced,
                    "progress": progress,
                }
            )
        return JsonResponse(
            {
                "status": "success",
                "data": {
                    "dashboardData": rows,
                    "machineData": [],
                    "scanLog": [],
                    "orderViewSummary": {},
                },
            }
        )

    if action == "scan":
        lot_no = request.POST.get("lot_no") or request.GET.get("lot_no")
        qty = int(request.POST.get("qty") or request.GET.get("qty") or 0)
        machine_no = (
            request.POST.get("machine_no")
            or request.GET.get("machine_no")
            or "MC-01"
        )
        try:
            lot = Lot.objects.get(lot_no=lot_no)
        except Lot.DoesNotExist:
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"Lot {lot_no} not found",
                },
                status=404,
            )
        ScanRecord.objects.create(lot=lot, machine_no=machine_no, qty=qty)
        lot.last_scan = now()
        lot.first_scan = lot.first_scan or lot.last_scan
        lot.save(update_fields=["first_scan", "last_scan"])
        return JsonResponse({"status": "success"})

    if action in ["getActiveUsers", "kickUser", "getQrExportData"]:
        return JsonResponse({"status": "success", "data": []})

    return JsonResponse(
        {"status": "error", "message": "Unknown action"}, status=400
    )


# ---------- Dashboard shortcuts (Overall / Preform) ----------


@login_required
def dashboard_overview(request):
    """
    Shortcut: Overall – List View
    /dashboard/overview/ -> /dashboard/?department=Overall&view=list
    """
    url = reverse("dashboard")
    return redirect(f"{url}?department=Overall&view=list")


@login_required
def dashboard_preform(request):
    """
    Shortcut: Preform – List View
    /dashboard/preform/ -> /dashboard/?department=Preform&view=list
    """
    url = reverse("dashboard")
    return redirect(f"{url}?department=Preform&view=list")


@login_required
def dashboard_overall_order(request):
    """
    Shortcut: Overall – Order View
    /dashboard/overall/order/ -> /dashboard/?department=Overall&view=order
    """
    url = reverse("dashboard")
    return redirect(f"{url}?department=Overall&view=order")


@login_required
def dashboard_preform_order(request):
    """
    Shortcut: Preform – Order View
    /dashboard/preform/order/ -> /dashboard/?department=Preform&view=order
    """
    url = reverse("dashboard")
    return redirect(f"{url}?department=Preform&view=order")

@login_required
def export_productivity_excel(request):
    # 1) รับ filter (เหมือนหน้า Dashboard)
    dept = request.GET.get("department", "Overall")
    machine_no_filter = request.GET.get("machine_no", "").strip()
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    # 2) Query ข้อมูลพื้นฐาน
    qs = Lot.objects.all()

    # Filter แผนก
    if dept == "Preform":
        qs = qs.filter(department__icontains="พรีฟอร์ม")
    elif dept != "Overall":
        qs = qs.filter(department__icontains=LABELS.get(dept, dept))

    # Filter เครื่อง
    if machine_no_filter:
        qs = qs.filter(machine_no__iexact=machine_no_filter)

    # Filter วันที่
    if date_from:
        qs = qs.filter(last_scan__date__gte=date_from)
    if date_to:
        qs = qs.filter(last_scan__date__lte=date_to)

    # Annotate ผลรวมการผลิต (ORM ลด Query)
    qs = _annotate_lots(qs).order_by("lot_no")

    # 3) สร้าง Excel Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productivity Report"

    headers = [
        "Lot No", "Part No", "Customer", "Department",
        "Machine", "Type", "Target", "Produced",
        "Progress (%)", "Boxes", "Status", "Last Scan"
    ]
    ws.append(headers)

    # 4) เติมข้อมูลทีละแถว
    for lot in qs:
        produced = lot.produced_qty or 0
        target = lot.target or lot.production_quantity or 0
        progress = (produced / target * 100) if target > 0 else 0

        # กล่อง
        boxes = int(produced / lot.pieces_per_box) if lot.pieces_per_box else 0

        # สถานะ
        if produced == 0:
            status = "Waiting"
        elif progress >= 100:
            status = "Finished"
        else:
            status = "Running"

        # เวลา Scan
        last_scan_str = lot.last_scan.strftime("%Y-%m-%d %H:%M") if lot.last_scan else ""

        ws.append([
            lot.lot_no,
            lot.part_no,
            lot.customer,
            lot.department,
            lot.machine_no,
            lot.type or "Order",
            target,
            produced,
            round(progress, 2),
            boxes,
            status,
            last_scan_str,
        ])

    # 5) ปรับความกว้างคอลัมน์ให้พอดี
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16

    # 6) ส่งกลับเป็นไฟล์ดาวน์โหลด
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    file_name = f"Productivity_Report_{now().strftime('%Y%m%d')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'

    wb.save(response)
    return response