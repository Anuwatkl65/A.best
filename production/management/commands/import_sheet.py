from django.core.management.base import BaseCommand
from production.models import Lot
import pandas as pd
from pandas import ExcelFile 
from pathlib import Path

# แผนที่ชื่อคอลัมน์ใน Excel/CSV -> ฟิลด์ใน Model
COLUMN_MAP = {
    "Lot No": "lot_no",
    "Part No": "part_no",
    "Customer": "customer",
    "Desc": "description",
    "Prod. Qty": "production_quantity",
    "Pcs/Box": "pieces_per_box",
    "Target": "target",
    "Department": "department",
    "Machine": "machine_no",
    "Type": "type",
    "First Scan": "first_scan",
    "Last Scan": "last_scan",
}

class Command(BaseCommand):  # <<== ต้องชื่อ Command และสืบทอด BaseCommand
    help = "Import lots from Excel/CSV into SQLite (update_or_create by lot_no)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to .xlsx or .csv file")
        parser.add_argument("--sheet", default=None, help="Sheet name for .xlsx")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        sheet = opts["sheet"]

        if not path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        # โหลดไฟล์
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            xls = ExcelFile(path)
        if sheet and sheet not in xls.sheet_names:
            self.stderr.write(self.style.ERROR(
            f"Worksheet '{sheet}' not found. Available: {xls.sheet_names}"
        ))
        return
        df = pd.read_excel(path, sheet_name=sheet or xls.sheet_names[0])

        # รีเนมคอลัมน์ให้ตรงกับฟิลด์ในโมเดล
        df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})

        created = updated = 0
        for _, row in df.iterrows():
            data = {field: row.get(field, None) for field in COLUMN_MAP.values()}
            lot_no = str(data.get("lot_no") or "").strip()
            if not lot_no:
                continue

            # คำนวณ target ถ้าไม่ส่งมา
            pq = int(data.get("production_quantity") or 0)
            ppb = int(data.get("pieces_per_box") or 0)
            if not int(data.get("target") or 0) and pq and ppb:
                data["target"] = pq // max(ppb, 1)

            obj, is_created = Lot.objects.update_or_create(
                lot_no=lot_no,
                defaults=data,
            )
            created += int(is_created)
            updated += int(not is_created)

        self.stdout.write(self.style.SUCCESS(
            f"Imported OK -> created: {created}, updated: {updated}"
        ))
