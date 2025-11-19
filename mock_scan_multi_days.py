# mock_scan_multi_days.py
from datetime import timedelta
import random

from django.utils.timezone import now
from production.models import Lot, ScanRecord


def run(lot_no="L002", days=20):
    """
    สร้าง Mock Scan ย้อนหลังหลายวันให้ Lot ที่ระบุ
    - lot_no : เลข Lot ที่ต้องการสร้างข้อมูล
    - days   : จำนวนวันย้อนหลัง (เช่น 20 = ย้อนหลัง 20 วัน)
    """
    try:
        lot = Lot.objects.get(lot_no=lot_no)
    except Lot.DoesNotExist:
        print(f"⚠️ ไม่พบ Lot {lot_no} ในระบบ")
        return

    print(f"เริ่มสร้าง mock สำหรับ {lot_no} ({days} วัน)...")

    # ลบข้อมูลเก่าก่อน กันข้อมูลซ้อน
    ScanRecord.objects.filter(lot=lot).delete()

    base_dt = now()              # วันที่/เวลา ณ ปัจจุบัน (timezone ถูกต้อง)

    scans = []
    for i in range(days):
        # ย้อนหลังออกไปทีละวัน
        day_dt = base_dt - timedelta(days=i)

        # สุ่มจำนวนครั้งที่สแกนต่อวัน (เช่น 1–4 ครั้ง)
        times_per_day = random.randint(1, 4)

        for _ in range(times_per_day):
            # เปลี่ยนเฉพาะเวลา แต่ "วัน" ยังเป็นของ day_dt
            scanned_at = day_dt.replace(
                hour=random.randint(7, 21),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                microsecond=0,
            )

            qty = random.randint(50, 300)

            scans.append(
                ScanRecord(
                    lot=lot,
                    machine_no=lot.machine_no or "MC-01",
                    qty=qty,
                    scanned_at=scanned_at,
                )
            )

    # บันทึกทีเดียว
    ScanRecord.objects.bulk_create(scans)

    # อัปเดต first_scan / last_scan ให้ Lot
    first = lot.scans.order_by("scanned_at").first()
    last = lot.scans.order_by("-scanned_at").first()
    if first:
        lot.first_scan = first.scanned_at
    if last:
        lot.last_scan = last.scanned_at
    lot.save(update_fields=["first_scan", "last_scan"])

    print(f"✅ สร้าง Mock Scan ให้ {lot_no} เสร็จแล้ว ({len(scans)} records)!")
