from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path("", views.index, name="home_menu"),
    path("home/", views.index, name="home_menu"),
    path("login/", views.login_page, name="login_page"),
    path("logout/", views.logout_view, name="logout"),

    # ใหม่: ไปหน้า Overall/Preform ตรงๆ
path("dashboard/overview/", views.dashboard_overview, name="dashboard_overview"),
path("dashboard/preform/", views.dashboard_preform, name="dashboard_preform"),

    # ของเดิม (ยังคงไว้ใช้งาน)
    path("department/", views.department_select, name="department_select"),
    path("view/", views.view_select, name="view_select"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("scan/", views.scan, name="scan"),
    path("qr-export/", views.qr_export, name="qr_export"),
    path("data-collect/", views.data_collect, name="data_collect"),
    path("user-control/", views.user_control, name="user_control"),
    path("api/", views.api, name="api"),
    path("dashboard/machine/<str:machine_no>/",views.machine_detail,name="machine_detail"),
    path("lot/<str:lot_no>/", views.lot_detail, name="lot_detail"),
]
