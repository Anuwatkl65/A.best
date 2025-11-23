from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils.timezone import now


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

    # เพิ่มตาม Databased sheet
    customer_part_no = models.CharField(max_length=100, blank=True, null=True)
    po_no = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)

    production_quantity = models.IntegerField(default=0)
    pieces_per_box = models.IntegerField(default=0)
    target = models.IntegerField(default=0)

    department = models.CharField(max_length=100, blank=True, null=True)
    machine_no = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)

    first_scan = models.DateTimeField(null=True, blank=True)
    last_scan = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.lot_no

    # ------------------- Computed Fields -------------------

    @property
    def produced(self):
        """ยอดผลิตรวมทั้งหมด (sum qty ของทุก scan)"""
        return self.scans.aggregate(total=Sum("qty"))["total"] or 0

    @property
    def progress(self):
        """เปอร์เซ็นต์ความคืบหน้า"""
        if (self.target or self.production_quantity) > 0:
            target = self.target or self.production_quantity
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
        if self.produced == 0:
            return "waiting"
        if self.progress >= 100:
            return "finished"
        return "running"


class ScanRecord(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="scans")
    machine_no = models.CharField(max_length=50, null=True, blank=True)
    qty = models.IntegerField(default=0)
    scanned_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.lot.lot_no} +{self.qty} @ {self.machine_no}"
