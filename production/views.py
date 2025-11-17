from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Lot, ScanRecord, UserProfile
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db.models import Sum, Q
from django.contrib.auth import logout
from django.shortcuts import redirect


def login_page(request):
    if request.user.is_authenticated:
        return redirect('home_menu')
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            return redirect('home_menu')
        return render(request, "production/login.html", {"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"})
    return render(request, "production/login.html")

def _is_staff_or_admin(user):
    if not user.is_authenticated: return False
    up = getattr(user, 'userprofile', None)
    return (up and up.role in ['admin', 'staff']) or user.is_staff or user.is_superuser

def logout_view(request):
    logout(request)
    # กลับไปหน้า login หรือหน้าเมนูหลัก ตามที่คุณต้องการ
    return redirect("login_page")   # ถ้าชื่อ url login เป็นอย่างอื่นก็เปลี่ยนตรงนี้

# ---------- Pages ----------
@login_required
def index(request):
    return render(request, "production/index.html")

@login_required
def department_select(request):
    return render(request, "production/department_select.html")

@login_required
def view_select(request):
    dept = request.GET.get("department", "Overall")
    # ถ้าเป็น Overall ให้ข้ามหน้าเลือกมุมมอง ไปที่ List View ทันที
    if dept.lower() == "overall":
        return redirect(f"{reverse('dashboard')}?department=Overall&view=list")

    return render(request, "production/view_select.html", {
        "department": dept,
        "department_label": {"Overall": "ภาพรวม", "Preform": "พรีฟอร์ม"}.get(dept, dept),
    })

@login_required
def dashboard(request):
    dept = request.GET.get("department", "Overall")
    view_type = request.GET.get("view", "list")
    machine_no_filter = request.GET.get("machine_no", "").strip()
    lot_type = request.GET.get("lot_type", "all")  # ใช้กับปุ่ม filter ด้านบน

    department_label_map = {
        "Overall": "ภาพรวม",
        "Preform": "พรีฟอร์ม",
    }
    department_label = department_label_map.get(dept, dept)

    # ---------- ดึงข้อมูล Lot ----------
    qs = Lot.objects.all()

    # filter ตามแผนก
    if dept == "Preform":
        qs = qs.filter(department__icontains="พรีฟอร์ม")
    elif dept == "Overall":
        pass
    else:
        qs = qs.filter(department__icontains=department_label)

    # filter ตามเครื่อง (ถ้าใช้จาก machine_detail)
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

    # เก็บ qs ต้นฉบับไว้ใช้สรุป count ด้านบน (ไม่ต้องถูก filter ด้วย lot_type)
    qs_for_counts = qs

    # ---------- filter ตาม type จากปุ่มด้านบน ----------
    active_type = lot_type  # ส่งไป template ใช้ไฮไลต์ปุ่ม
    if lot_type != "all":
        # map เป็นชื่อ type ในฐานข้อมูล (Order / Sample / Reserved / Extra / Claim)
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

    # ---------- สรุปตาม type (ใช้ qs_for_counts) ----------
    type_counts = {
        "all": qs_for_counts.count(),
        "order": qs_for_counts.filter(type__iexact="Order").count(),
        "sample": qs_for_counts.filter(type__iexact="Sample").count(),
        "reserved": qs_for_counts.filter(type__iexact="Reserved").count(),
        "extra": qs_for_counts.filter(type__iexact="Extra").count(),
        "claim": qs_for_counts.filter(type__iexact="Claim").count(),
    }

    # ---------- เตรียม lots + summary (ใช้ qs ที่ถูก filter แล้ว) ----------
    lots = []
    waiting = 0
    in_progress = 0
    finished = 0

    for lot in qs.order_by("lot_no"):
        produced = lot.scans.aggregate(s=Sum("qty"))["s"] or 0
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

    # ---------- กลุ่มตาม type (ใช้กับ Order View) ----------
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
        "active_type": active_type,  # <-- ใช้ใน template ที่คุณส่งมาให้ดู
    }
    return render(request, template_name, context)



@login_required
def machine_detail(request, machine_no):
    dept = request.GET.get("department", "Preform")

    qs = Lot.objects.filter(
        department__icontains="พรีฟอร์ม" if dept == "Preform" else dept,
        machine_no__iexact=machine_no,
    ).order_by("lot_no")

    # ใช้ logic เดิมสร้าง lots / summary อีกที
    lots = []
    waiting = 0
    in_progress = 0
    finished = 0

    for lot in qs:
        produced = lot.scans.aggregate(s=Sum("qty"))["s"] or 0
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

    ctx = {
        "department": dept,
        "department_label": {"Overall": "ภาพรวม", "Preform": "พรีฟอร์ม"}.get(dept, dept),
        "view_type": "list",
        "machine_no": machine_no,
        "lots": lots,
        "summary": summary,
        "type_counts": {
            "all": qs.count(),
            "order": qs.filter(type__iexact="Order").count(),
            "sample": qs.filter(type__iexact="Sample").count(),
            "reserved": qs.filter(type__iexact="Reserved").count(),
            "extra": qs.filter(type__iexact="Extra").count(),
            "claim": qs.filter(type__iexact="Claim").count(),
        },
    }

    return render(request, "production/dashboard_list.html", ctx)

def _build_dashboard_summary(qs):
    total = qs.count()
    order = qs.filter(type="Order").count()
    sample = qs.filter(type="Sample").count()
    reserved = qs.filter(type="Reserved").count()
    extra = qs.filter(type="Extra").count()
    claim = qs.filter(type="Claim").count()
    finished = qs.filter(progress=100).count()  # แล้วแต่เงื่อนไขที่คุณใช้
    waiting = total - finished

    return {
        "count_all": total,
        "count_order": order,
        "count_sample": sample,
        "count_reserved": reserved,
        "count_extra": extra,
        "count_claim": claim,
        "count_waiting": waiting,
        "count_finished": finished,
    }
    

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

    # log การสแกนทั้งหมด (ไว้โชว์ตารางด้านล่าง)
    scan_logs = lot.scans.order_by("scanned_at")

    # summary สำหรับหัวหน้า dashboard ด้านบน (จะใช้ component เดียวกัน)
    summary = {
        "total_lots": 1,
        "waiting": 1 if produced == 0 else 0,
        "in_progress": 1 if 0 < progress < 100 else 0,
        "finished": 1 if progress >= 100 else 0,
    }
    type_counts = {
        "all": 1,
        "order": 1 if (lot.type or "").lower() == "order" else 0,
        "sample": 1 if (lot.type or "").lower() == "sample" else 0,
        "reserved": 1 if (lot.type or "").lower() == "reserved" else 0,
        "extra": 1 if (lot.type or "").lower() == "extra" else 0,
        "claim": 1 if (lot.type or "").lower() == "claim" else 0,
    }

    ctx = {
        "department": dept,
        "department_label": department_label,
        "view_type": "list",
        "lot": lot,
        "produced": produced,
        "target": target,
        "progress": progress,
        "boxes": boxes,
        "summary": summary,
        "type_counts": type_counts,
        "scan_logs": scan_logs,
    }
    return render(request, "production/lot_detail.html", ctx)


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

# ---------- API (mock คงโค้ดเดิม) ----------
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
        return JsonResponse({"status": "error", "message": "Missing action"}, status=400)

    # คง mock login ไว้เพื่อรองรับฟรอนต์เดิม (แต่หน้าเว็บหลักจะใช้ Auth จริงแล้ว)
    if action == "login":
        user = request.POST.get("user") or request.GET.get("user")
        password = request.POST.get("password") or request.GET.get("password")
        ok = (user in ["admin", "staff", "visitor"]) and (password == "1234")
        if ok:
            return JsonResponse({
                "status": "success",
                "user": {"name": user.title(), "username": user, "role": user},
                "token": "demo-token",
            })
        return JsonResponse({"status": "error", "message": "Invalid credentials"}, status=401)

    if action == "getData":
        _mock_if_empty()
        rows = []
        for lot in Lot.objects.all().order_by("lot_no"):
            produced = lot.scans.aggregate(s=Sum("qty"))["s"] or 0
            progress = 0 if not lot.target else min(100, int(produced * 100 / lot.target))
            rows.append({
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
                "firstScan": lot.first_scan.isoformat() if lot.first_scan else None,
                "lastScan": lot.last_scan.isoformat() if lot.last_scan else None,
                "scannedCount": produced,
                "progress": progress,
            })
        return JsonResponse({"status": "success","data": {
            "dashboardData": rows, "machineData": [], "scanLog": [], "orderViewSummary": {}
        }})

    if action == "scan":
        lot_no = request.POST.get("lot_no") or request.GET.get("lot_no")
        qty = int(request.POST.get("qty") or request.GET.get("qty") or 0)
        machine_no = request.POST.get("machine_no") or request.GET.get("machine_no") or "MC-01"
        try:
            lot = Lot.objects.get(lot_no=lot_no)
        except Lot.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Lot {lot_no} not found"}, status=404)
        ScanRecord.objects.create(lot=lot, machine_no=machine_no, qty=qty)
        lot.last_scan = now()
        lot.first_scan = lot.first_scan or lot.last_scan
        lot.save(update_fields=["first_scan", "last_scan"])
        return JsonResponse({"status": "success"})

    if action in ["getActiveUsers", "kickUser", "getQrExportData"]:
        return JsonResponse({"status": "success", "data": []})

    return JsonResponse({"status": "error", "message": "Unknown action"}, status=400)

@login_required
def dashboard_overview(request):
    return render(request, "production/dashboard.html", {"department": "Overall"})

@login_required
def dashboard_preform(request):
    return render(request, "production/dashboard.html", {"department": "Preform"})

LABELS = {"Overall": "ภาพรวม", "Preform": "พรีฟอร์ม"}

