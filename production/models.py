# The above code defines Django models for managing departments, user profiles, machines, lots, scan
# records, and downtime logs with various properties and methods for tracking production data.
# production/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils.timezone import now
from django.utils import timezone


class Department(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("viewer", "Viewer"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="viewer")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Machine(models.Model):
    """ใช้เก็บข้อมูลจากชีท Machine List"""

    machine_no = models.CharField(max_length=50, unique=True)
    machine_name = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.machine_no} - {self.machine_name}"


class Lot(models.Model):
    lot_no = models.CharField(max_length=100, unique=True)
    part_no = models.CharField(max_length=100, blank=True, null=True)
    customer = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    # ข้อมูลประกอบอื่น ๆ (เผื่อใช้ในอนาคต)
    customer_part_no = models.CharField(max_length=100, blank=True, null=True)
    po_no = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)

    # จำนวนผลิต / เป้า
    production_quantity = models.IntegerField(default=0)
    pieces_per_box = models.IntegerField(default=0)
    target = models.IntegerField(default=0)

    # ผูกกับสายการผลิต
    department = models.CharField(max_length=100, blank=True, null=True)
    machine_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)

    # ---------- โหมดการทำงานหลัก (Setup / Production) ----------
    OEE_MODE_SETUP = "setup"
    OEE_MODE_PRODUCTION = "production"

    OEE_MODE_CHOICES = [
        (OEE_MODE_SETUP, "Setup"),
        (OEE_MODE_PRODUCTION, "Production"),
    ]

    operation_mode = models.CharField(
        max_length=20,
        choices=OEE_MODE_CHOICES,
        default=OEE_MODE_PRODUCTION,
        verbose_name="โหมดการทำงานปัจจุบัน (Setup/Production)",
    )

    # ---------- โหมดที่พนักงานเลือกตอนเดินเครื่อง (เช่น Auto / Manual / Trial) ----------
    RUN_MODE_AUTO = "auto"
    RUN_MODE_MANUAL = "manual"
    RUN_MODE_TRIAL = "trial"

    RUN_MODE_CHOICES = [
        (RUN_MODE_AUTO, "Auto"),
        (RUN_MODE_MANUAL, "Manual"),
        (RUN_MODE_TRIAL, "Trial"),
    ]

    run_mode = models.CharField(
        max_length=20,
        choices=RUN_MODE_CHOICES,
        blank=True,
        null=True,
        verbose_name="โหมดเดินเครื่องล่าสุด (Auto/Manual/Trial)",
        help_text="เก็บโหมดที่เลือกจากหน้า Operator ตอนกด Start / Continue",
    )

    # ---------- เวลา Scan จากระบบ ----------
    first_scan = models.DateTimeField(null=True, blank=True)
    last_scan = models.DateTimeField(null=True, blank=True)

    # ---------- เวลา OEE (ใช้กับ START / END) ----------
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.lot_no

    # ------------------- Computed Fields (Production) -------------------
    @property
    def produced(self):
        """ยอดผลิตรวมทั้งหมด (sum qty ของทุก scan)"""
        return self.scans.aggregate(total=Sum("qty"))["total"] or 0

    @property
    def progress(self):
        """เปอร์เซ็นต์ความคืบหน้า"""
        target = self.target or self.production_quantity
        if target > 0:
            return min(100, int(self.produced * 100 / target))
        return 0

    @property
    def boxes(self):
        """จำนวนกล่องที่บรรจุได้ตาม pieces_per_box"""
        if self.pieces_per_box:
            return int(self.produced / self.pieces_per_box)
        return 0

    @property
    def status(self):
        """สถานะ lot: waiting / running / finished"""
        if self.end_time:
            return "finished"
        if self.start_time:
            return "running"
        if self.produced == 0:
            return "waiting"
        if self.progress >= 100:
            return "finished"
        return "running"

    # ------------------- Computed Fields (OEE / Time Tracking) -------------------
    @property
    def total_time_seconds(self):
        """เวลารวมทั้งหมด (วินาที): ตั้งแต่กด Start จนถึง End (หรือปัจจุบัน)"""
        if not self.start_time:
            return 0
        cutoff = self.end_time or timezone.now()
        return int((cutoff - self.start_time).total_seconds())

    @property
    def total_downtime_seconds(self):
        """เวลารวมที่หยุดเครื่อง (วินาที): ผลรวมของ DowntimeLogs ทั้งหมด"""
        total = 0
        for log in self.downtime_logs.all():
            end = log.end_time or timezone.now()
            if end > log.start_time:  # กันเวลาติดลบ
                total += (end - log.start_time).total_seconds()
        return int(total)

    @property
    def runtime_seconds(self):
        """เวลาเดินเครื่องจริง (วินาที): เวลารวม - เวลาหยุด"""
        val = self.total_time_seconds - self.total_downtime_seconds
        return max(0, int(val))

    # ---- minutes (เผื่อหน้าเก่ายังใช้) ----
    @property
    def total_time_minutes(self):
        return self.total_time_seconds // 60

    @property
    def total_downtime_minutes(self):
        return self.total_downtime_seconds // 60

    @property
    def runtime_minutes(self):
        return self.runtime_seconds // 60

    @property
    def availability_percent(self):
        """ค่า A (Availability) % ใช้ seconds ในการคำนวณ"""
        if self.total_time_seconds == 0:
            return 0
        return round((self.runtime_seconds / self.total_time_seconds) * 100, 1)

    # --- Helper สำหรับแสดงผลเป็น ชม. นาที วินาที ---
    def _format_seconds(self, seconds: int) -> str:
        s = int(max(0, seconds))
        h = s // 3600
        m = (s % 3600) // 60
        r = s % 60

        if h > 0:
            return f"{h} ชม. {m} น. {r} วินาที"
        if m > 0:
            return f"{m} น. {r} วินาที"
        return f"{r} วินาที"

    @property
    def display_total_time(self):
        return self._format_seconds(self.total_time_seconds)

    @property
    def display_downtime(self):
        return self._format_seconds(self.total_downtime_seconds)

    @property
    def display_runtime(self):
        return self._format_seconds(self.runtime_seconds)


class ScanRecord(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="scans")
    machine_no = models.CharField(max_length=50, null=True, blank=True)
    qty = models.IntegerField(default=0)
    scanned_at = models.DateTimeField(default=now)

    # --- เพิ่มบรรทัดนี้ครับ ---
    sticker_unique_id = models.CharField(max_length=50, blank=True, null=True, help_text="เก็บเลข Unique ID จาก QR Code ป้องกันซ้ำ")

    def __str__(self):
        return f"{self.lot.lot_no} +{self.qty} @ {self.machine_no}"


# === ตารางเก็บประวัติการหยุดเครื่อง (Downtime) ===
class DowntimeLog(models.Model):
    lot = models.ForeignKey(
        Lot, on_delete=models.CASCADE, related_name="downtime_logs"
    )
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มหยุด")
    end_time = models.DateTimeField(
        null=True, blank=True, verbose_name="เวลากลับมาทำต่อ"
    )
    reason = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="สาเหตุ"
    )

    def __str__(self):
        return f"{self.lot.lot_no} Break: {self.start_time.strftime('%H:%M')}"

    @property
    def duration_seconds(self):
        """คำนวณเวลาหยุดของครั้งนี้ (วินาที)"""
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds())

    @property
    def duration_minutes(self):
        """คำนวณเวลาหยุดของครั้งนี้ (นาที จากวินาที)"""
        return self.duration_seconds // 60
