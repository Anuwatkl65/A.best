from django.utils.timezone import now
from datetime import timedelta
import random

from production.models import Lot, ScanRecord


def create_mock_scans_for_lot(lot, days=30):
    """
    สร้าง Mock Scan ให้ Lot เดียว
    - ลบ ScanRecord เดิมของ lot นี้ก่อน
    - ใส่ข้อมูลใหม่ย้อนหลัง N วัน
    """
    print(f"- สร้าง Mock Scan ให้ {lot.lot_no} ...")

    # ลบข้อมูลเดิมของ lot นี้ (กันข้อมูลซ้ำ/มั่ว)
    ScanRecord.objects.filter(lot=lot).delete()

    base = now()
    scans = []

    # ถ้ามี target ให้กระจาย qty ตามเป้า / days + random
    target = lot.target or lot.production_quantity or 0
    base_per_day = target // days if target > 0 else 150  # ถ้าไม่มีเป้า ใช้ 150 เป็นค่าเฉลี่ย

    running_total = 0

    for i in range(days):
        # ไล่วันจากเก่าสุด -> ใหม่สุด
        day = base - timedelta(days=(days - 1 - i))

        # random รอบ base_per_day ให้กราฟมีขึ้นลง
        qty = max(0, int(random.gauss(base_per_day, base_per_day * 0.3)))
        if qty == 0:
            qty = random.randint(50, 250)

        # ไม่จำเป็นต้องจำกัดไม่ให้เกิน target รวม แต่อยากจำกัดก็ได้
        running_total += qty

        scans.append(
            ScanRecord(
                lot=lot,
                machine_no=lot.machine_no or "MC-01",
                qty=qty,
                scanned_at=day.replace(
                    hour=random.randint(7, 21),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                    microsecond=0,
                ),
            )
        )

    # สร้างทีเดียวรวดเดียว
    ScanRecord.objects.bulk_create(scans)

    # อัปเดต first_scan / last_scan ของ Lot
    first = lot.scans.order_by("scanned_at").first()
    last = lot.scans.order_by("-scanned_at").first()

    if first:
        lot.first_scan = first.scanned_at
    if last:
        lot.last_scan = last.scanned_at
    lot.save(update_fields=["first_scan", "last_scan"])

    print(f"  ✅ {lot.lot_no}: สร้าง {len(scans)} แถวเรียบร้อย!")


def run(days=30):
    """
    ฟังก์ชันหลัก: สร้าง Mock Scan ให้ทุก Lot ในระบบ
    ใช้ใน shell ด้วยคำสั่ง:ปx
        from mock_scan import run
        run()          # หรือ run(60) ถ้าอยากได้ 60 วัน
    """
    lots = Lot.objects.all().order_by("lot_no")

    if not lots.exists():
        print("ยังไม่มี Lot ในระบบเลย")
        return

    print(f"เริ่มสร้าง Mock Scan ให้ทั้งหมด {lots.count()} lots (ย้อนหลัง {days} วัน)...")

    for lot in lots:
        create_mock_scans_for_lot(lot, days=days)

    print("🎉 เสร็จแล้วครับ!")
