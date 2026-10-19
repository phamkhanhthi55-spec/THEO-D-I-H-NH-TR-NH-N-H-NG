@echo off
chcp 65001 > nul
title Máy chủ Web & Điện thoại - Theo dõi đơn hàng
echo ========================================================
echo    🎀 MÁY CHỦ WEB & ĐIỆN THOẠI - THEO DÕI ĐƠN HÀNG 🎀
echo ========================================================
echo.
cd /d "%~dp0"
echo [1] Đang mở trình duyệt máy tính...
start "" http://127.0.0.1:8000
echo [2] Đang khởi động máy chủ phục vụ điện thoại...
echo.
echo ========================================================
echo  📱 Bạn mở nút "Quét mã QR" trên trang web bằng điện thoại
echo  hoặc nhập địa chỉ IP hiển thị trên trang để dùng nhé!
echo ========================================================
echo.
py -3 -m uvicorn web.app:app --host 0.0.0.0 --port 8000
pause
