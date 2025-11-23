from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="home_menu"),
    path("home/", views.index, name="home_menu"),
    path("login/", views.login_page, name="login_page"),
    path("logout/", views.logout_view, name="logout"),

    # Shortcuts – List View
    path("dashboard/overview/", views.dashboard_overview, name="dashboard_overview"),
    path("dashboard/preform/", views.dashboard_preform, name="dashboard_preform"),

    # Shortcuts – Order View
    path("dashboard/overall/order/",views.dashboard_overall_order,name="dashboard_overall_order",),
    path("dashboard/preform/order/",views.dashboard_preform_order,name="dashboard_preform_order",),

    # เลือกแผนก/มุมมอง + dashboard หลัก
    path("department/", views.department_select, name="department_select"),
    path("view/", views.view_select, name="view_select"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("lot/<str:lot_no>/chart-data/", views.lot_chart_data, name="lot_chart_data"),
    path("productivity/", views.productivity_form, name="productivity_form"),
    path("productivity/report/", views.productivity_view, name="productivity_view"),



    # Lot detail
    path("lot/<str:lot_no>/", views.lot_detail, name="lot_detail"),

    # Machine detail
    path("dashboard/machine/<str:machine_no>/",views.machine_detail,name="machine_detail",
    ),

    # อื่น ๆ
    path("scan/", views.scan, name="scan"),
    path("qr-export/", views.qr_export, name="qr_export"),
    path("data-collect/", views.data_collect, name="data_collect"),
    path("user-control/", views.user_control, name="user_control"),
    path("api/", views.api, name="api"),
    path("export/productivity/",views.export_productivity_excel,name="export_productivity_excel",),

    # import Excel
    path("import-excel/", views.import_excel, name="import_excel"),
]
