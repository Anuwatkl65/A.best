import time

from django.conf import settings
from django.contrib.auth import logout


class IdleTimeoutMiddleware:
    """
    ถ้าผู้ใช้ไม่ได้ใช้งาน (ไม่มี request) นานเกิน IDLE_SESSION_TIMEOUT วินาที
    จะ logout อัตโนมัติ
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # ถ้าไม่ได้ตั้งไว้ใน settings จะใช้ค่า default = 1800 วินาที (30 นาที)
        self.timeout = getattr(settings, "IDLE_SESSION_TIMEOUT", 1800)

    def __call__(self, request):
        # ถ้ายังไม่ได้ login ไม่ต้องเช็คอะไร
        if request.user.is_authenticated:
            current_ts = int(time.time())
            last_ts = request.session.get("last_activity_ts", current_ts)

            # ถ้าไม่ได้ขยับเกิน timeout → logout
            if current_ts - last_ts > self.timeout:
                logout(request)
                # ล้าง session ทิ้งกันงง
                request.session.flush()
            else:
                # ยังไม่เกินเวลา → อัปเดต timestamp
                request.session["last_activity_ts"] = current_ts

        response = self.get_response(request)
        return response
