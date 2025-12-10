import os
import pandas as pd

from django.core.management.base import BaseCommand
from production.models import Lot


class Command(BaseCommand):
    help = "อัปเดต Target และ Production Quantity ของ Lot จากไฟล์ Excel"

    def handle(self, *args, **options):
        # ---- 1) ระบุ path ไฟล์ Excel ----
        # ถ้าคุณวางไฟล์ไว้ในโฟลเดอร์เดียวกับ manage.py (C:\tracker)
        excel_path = os.path.join(os.getcwd(), "A.Best - Production Tracker.xlsx")

        if not os.path.exists(excel_path):
            self.stdout.write(self.style.ERROR(f"ไม่พบไฟล์: {excel_path}"))
            return

        # ---- 2) อ่านชีท Databased ----
        df = pd.read_excel(excel_path, sheet_name="Databased")
        self.stdout.write(self.style.SUCCESS(f"โหลด Excel แล้ว {len(df)} แถว (ชีท Databased)"))

        updated = 0
        skipped = 0

        for idx, row in df.iterrows():
            # ---- 3) ดึง Lot No. (มีจุด) ----
            lot_no = str(row.get("Lot No.", "")).strip()

            # ข้ามแถวที่ไม่มี Lot No
            if not lot_no or lot_no.lower() == "nan":
                skipped += 1
                continue

            # ---- 4) หา Lot ใน DB ----
            try:
                lot = Lot.objects.get(lot_no=lot_no)
            except Lot.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"[MISS] ไม่พบ Lot ใน DB: {lot_no}"))
                skipped += 1
                continue

            # ---- 5) ดึง Target จาก Excel ----
            raw_target = row.get("Target", None)

            # ถ้า Target ว่าง → ใช้ Production Quantity แทน
            if pd.isna(raw_target) or not raw_target:
                raw_target = row.get("Production Quantity", 0)

            try:
                target = int(raw_target or 0)
            except (ValueError, TypeError):
                self.stdout.write(
                    self.style.WARNING(
                        f"[WARN] Target ไม่ใช่ตัวเลข (Lot {lot_no}): {raw_target!r}"
                    )
                )
                skipped += 1
                continue

            fields = []

            # ---- 6) อัปเดต lot.target ----
            if (lot.target or 0) != target:
                lot.target = target
                fields.append("target")

            # ---- 7) อัปเดต lot.production_quantity ให้เท่ากับ target ด้วย ----
            if (lot.production_quantity or 0) != target:
                lot.production_quantity = target
                fields.append("production_quantity")

            # ---- 8) save ถ้ามี field ให้เปลี่ยน ----
            if fields:
                lot.save(update_fields=fields)
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Lot {lot_no}: target={lot.target}, prod_qty={lot.production_quantity}"
                    )
                )
            else:
                skipped += 1  # ไม่มีอะไรเปลี่ยน

        # ---- 9) สรุปผล ----
        self.stdout.write(
            self.style.SUCCESS(
                f"อัปเดตสำเร็จ: {updated} รายการ / ข้าม: {skipped} รายการ"
            )
        )
