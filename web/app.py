"""
Web App Backend cho ứng dụng Theo dõi hành trình đơn hàng (Hello Kitty Pastel).
Hỗ trợ mở và sử dụng trực tiếp trên điện thoại (iPhone, Android) và trình duyệt máy tính.
"""

import os
import sys
import json
import socket
import asyncio
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Thêm thư mục gốc vào sys.path để import src
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.database import DatabaseManager
from src.carrier import detect_carrier, get_carrier_name, CARRIER_SPX, CARRIER_GHN, CARRIER_UNKNOWN
from src.tracking import track_order

app = FastAPI(title="Theo dõi hành trình đơn hàng - Web & Mobile")

# Database manager
db = DatabaseManager()

# Tracking progress tracker
tracking_state = {
    "is_tracking": False,
    "current": 0,
    "total": 0,
    "message": "",
    "success_count": 0,
    "fail_count": 0
}


def get_local_ip():
    """Lấy địa chỉ IP nội bộ của máy tính trong mạng WiFi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_status_priority(journey_status):
    """
    Quy tắc thứ tự hiển thị:
    - 0: Đơn hàng thông thường (chưa tra cứu, đang xử lý, trung chuyển, đang lấy hàng...) -> Ở TRÊN CÙNG
    - 1: 'Đang giao hàng' -> ĐẨY XUỐNG KỀ CUỐI
    - 2: 'Giao hàng thành công' -> ĐẨY XUỐNG CUỐI CÙNG
    """
    if not journey_status:
        return 0
    s = str(journey_status).strip().lower()
    if any(w in s for w in ["giao hàng thành công", "giao thành công", "đã giao thành công", "đã giao"]):
        return 2
    if any(w in s for w in ["đang giao hàng", "đang giao", "nhân viên đang giao", "đang đi giao"]):
        return 1
    return 0


class OrderCreate(BaseModel):
    account_name: Optional[str] = ""
    product_name: Optional[str] = ""
    tracking_code: Optional[str] = ""
    carrier: Optional[str] = ""
    amount: Optional[float] = 0.0
    amount_text: Optional[str] = ""
    address: Optional[str] = ""
    phone_last4: Optional[str] = ""


class OrderUpdate(BaseModel):
    account_name: Optional[str] = None
    product_name: Optional[str] = None
    tracking_code: Optional[str] = None
    carrier: Optional[str] = None
    amount: Optional[float] = None
    amount_text: Optional[str] = None
    address: Optional[str] = None
    phone_last4: Optional[str] = None
    journey_status: Optional[str] = None


@app.get("/api/info")
def get_info():
    """Lấy thông tin mạng WiFi để điện thoại kết nối."""
    ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    return {
        "ip": ip,
        "port": port,
        "url": f"http://{ip}:{port}"
    }


@app.get("/api/orders")
def list_orders(search: str = "", carrier_filter: str = "ALL"):
    """
    Lấy danh sách đơn hàng đã được phân loại:
    - Đơn thường ở trên
    - 'Đang giao hàng' kề cuối
    - 'Giao hàng thành công' dưới cùng
    - Cột STT luôn đánh số 1, 2, 3... liên tục
    """
    raw_orders = db.get_all_orders()
    filtered = []

    for o in raw_orders:
        d = dict(o)
        # Lọc theo carrier
        if carrier_filter and carrier_filter != "ALL":
            if carrier_filter == "UNKNOWN":
                if d.get("carrier") and d["carrier"] != CARRIER_UNKNOWN:
                    continue
            elif d.get("carrier") != carrier_filter:
                continue

        # Lọc theo từ khóa tìm kiếm
        if search:
            kw = search.strip().lower()
            acc = (d.get("account_name") or "").lower()
            prod = (d.get("product_name") or "").lower()
            code = (d.get("tracking_code") or "").lower()
            status = (d.get("journey_status") or "").lower()
            addr = (d.get("address") or "").lower()
            if kw not in acc and kw not in prod and kw not in code and kw not in status and kw not in addr:
                continue

        filtered.append(d)

    # Phân nhóm theo thứ tự ưu tiên
    g0 = [o for o in filtered if get_status_priority(o.get("journey_status", "")) == 0]
    g1 = [o for o in filtered if get_status_priority(o.get("journey_status", "")) == 1]
    g2 = [o for o in filtered if get_status_priority(o.get("journey_status", "")) == 2]

    # Sắp xếp nội bộ từng nhóm theo ID
    g0.sort(key=lambda x: x.get("id", 0))
    g1.sort(key=lambda x: x.get("id", 0))
    g2.sort(key=lambda x: x.get("id", 0))

    sorted_orders = g0 + g1 + g2

    # Gán số thứ tự STT liên tục từ 1 đến N
    for index, item in enumerate(sorted_orders, start=1):
        item["stt"] = index

    return sorted_orders


@app.post("/api/orders")
def create_order(data: OrderCreate):
    """Thêm đơn hàng mới."""
    carrier = data.carrier or detect_carrier(data.tracking_code or "")
    new_id = db.add_order(
        account_name=data.account_name or "",
        product_name=data.product_name or "",
        tracking_code=data.tracking_code or "",
        carrier=carrier,
        amount=data.amount or 0.0,
        amount_text=data.amount_text or "",
        phone_last4=data.phone_last4 or "",
        address=data.address or ""
    )
    return {"id": new_id, "success": True}


@app.put("/api/orders/{order_id}")
def update_order(order_id: int, data: OrderUpdate):
    """Cập nhật thông tin đơn hàng."""
    existing = db.get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    existing_dict = dict(existing)
    fields = {}

    for k, v in data.dict(exclude_unset=True).items():
        if v is not None:
            fields[k] = v

    # Tự động nhận diện carrier nếu thay đổi tracking_code mà chưa có carrier
    if "tracking_code" in fields and ("carrier" not in fields or not fields["carrier"]):
        fields["carrier"] = detect_carrier(fields["tracking_code"])

    # Cập nhật các trường
    db.update_order(
        order_id=order_id,
        account_name=fields.get("account_name", existing_dict.get("account_name", "")),
        product_name=fields.get("product_name", existing_dict.get("product_name", "")),
        tracking_code=fields.get("tracking_code", existing_dict.get("tracking_code", "")),
        carrier=fields.get("carrier", existing_dict.get("carrier", "")),
        amount=fields.get("amount", existing_dict.get("amount", 0.0)),
        amount_text=fields.get("amount_text", existing_dict.get("amount_text", "")),
        phone_last4=fields.get("phone_last4", existing_dict.get("phone_last4", "")),
        address=fields.get("address", existing_dict.get("address", ""))
    )

    if "journey_status" in fields:
        db.update_journey(order_id, fields["journey_status"], existing_dict.get("journey_detail", ""))

    return {"success": True}


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int):
    """Xóa 1 đơn hàng."""
    db.delete_order(order_id)
    return {"success": True}


def run_track_single(order_id: int, tracking_code: str, carrier: str, phone_last4: str):
    """Chạy tra cứu đơn hàng trong background thread."""
    try:
        result = track_order(tracking_code, carrier, phone_last4)
        if result.success:
            db.update_journey(order_id, result.status, result.detail)
        else:
            db.update_query_error(order_id, result.error)
    except Exception as e:
        db.update_query_error(order_id, str(e))


@app.post("/api/track/{order_id}")
def track_single_order(order_id: int, background_tasks: BackgroundTasks):
    """Tra cứu 1 đơn hàng."""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    code = order["tracking_code"]
    carrier = order["carrier"] or detect_carrier(code)
    phone = order["phone_last4"] or ""

    background_tasks.add_task(run_track_single, order_id, code, carrier, phone)
    return {"message": "Đang tra cứu trong nền...", "success": True}


def run_track_all_worker():
    """Worker tra cứu tất cả đơn hàng tuần tự."""
    global tracking_state
    orders = db.get_all_orders()
    to_track = [dict(o) for o in orders if o.get("tracking_code")]

    tracking_state["is_tracking"] = True
    tracking_state["total"] = len(to_track)
    tracking_state["current"] = 0
    tracking_state["success_count"] = 0
    tracking_state["fail_count"] = 0

    for idx, o in enumerate(to_track, start=1):
        tracking_state["current"] = idx
        code = o["tracking_code"]
        carrier = o.get("carrier") or detect_carrier(code)
        phone = o.get("phone_last4") or ""

        tracking_state["message"] = f"Đang tra cứu {idx}/{len(to_track)}: {code} ({get_carrier_name(carrier)})"
        try:
            res = track_order(code, carrier, phone)
            if res.success:
                db.update_journey(o["id"], res.status, res.detail)
                tracking_state["success_count"] += 1
            else:
                db.update_query_error(o["id"], res.error)
                tracking_state["fail_count"] += 1
        except Exception as e:
            db.update_query_error(o["id"], str(e))
            tracking_state["fail_count"] += 1

    tracking_state["is_tracking"] = False
    tracking_state["message"] = f"Hoàn tất: {tracking_state['success_count']} thành công, {tracking_state['fail_count']} lỗi."


@app.post("/api/track-all")
def track_all_orders(background_tasks: BackgroundTasks):
    """Tra cứu toàn bộ đơn hàng."""
    global tracking_state
    if tracking_state["is_tracking"]:
        return {"message": "Đang có tiến trình tra cứu đang chạy...", "running": True}

    background_tasks.add_task(run_track_all_worker)
    return {"message": "Đã bắt đầu tra cứu tất cả đơn hàng", "success": True}


@app.get("/api/track-status")
def get_track_status():
    """Lấy trạng thái tiến trình tra cứu."""
    return tracking_state


# Gắn thư mục tĩnh
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    """Trả về giao diện Web App Hello Kitty."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Web UI is ready to build"})
