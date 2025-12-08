from django.contrib import admin
from .models import Lot, ScanRecord, Department, UserProfile


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    # ตัด target / first_scan / last_scan ออกก่อน ให้ system check ผ่าน
    list_display = (
        "lot_no",
        "part_no",
        "customer",
        "department",
        "machine_no",
        "type",
    )
    search_fields = ("lot_no", "part_no", "customer", "machine_no")
    list_filter = ("department", "machine_no", "type")


@admin.register(ScanRecord)
class ScanRecordAdmin(admin.ModelAdmin):
    list_display = ("lot", "machine_no", "qty", "scanned_at")
    list_filter = ("machine_no", "scanned_at")
    search_fields = ("lot__lot_no",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department")
    list_filter = ("role", "department")
    search_fields = ("user__username",)
