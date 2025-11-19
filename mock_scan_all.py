# mock_scan_all.py
from django.utils.timezone import now
from datetime import timedelta
from production.models import Lot, ScanRecord
import random


def create_mock_scans_for_all(days=30):
    """
    ลบ ScanRecord เดิมของทุก Lot แล้วสร้าง mock scan ย้อนหลัง N วัน
    ใช้สำหรับเดโมกราฟเท่านั้น ห้ามใช้ในโปรดักชันจริง
    """
    base = now()

    for lot in Lot.objects.all():
        print(f"เริ่มสร้าง mock scan ให้ {lot.lot_no} ...")

        # ลบ log เดิมของ lot นั้นก่อน
        ScanRecord.objects.filter(lot=lot).delete()

        scans = []

        # ย้อนหลัง days วัน (เรียงจากเก่ามาหาใหม่ให้กราฟอ่านง่าย)
        for i in range(days):
            day = base - timedelta(days=(days - 1 - i))

            qty = random.randint(80, 300)  # ปริมาณต่อวันแบบสุ่ม

            scanned_at = day.replace(
                hour=random.randint(7, 21),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                microsecond=0,
            )

            scans.append(
                ScanRecord(
                    lot=lot,
                    machine_no=lot.machine_no or "MC-01",
                    qty=qty,
                    scanned_at=scanned_at,
                )
            )

        ScanRecord.objects.bulk_create(scans)

        # อัปเดต first_scan / last_scan ของ Lot
        first = lot.scans.order_by("scanned_at").first()
        last = lot.scans.order_by("-scanned_at").first()

        if first:
            lot.first_scan = first.scanned_at
        if last:
            lot.last_scan = last.scanned_at
        lot.save(update_fields=["first_scan", "last_scan"])

        print(f"✅ {lot.lot_no} สร้าง mock scan {len(scans)} แถวเรียบร้อย")


def run():
    # เรียกฟังก์ชันหลัก (30 วัน)
    create_mock_scans_for_all(days=30)
