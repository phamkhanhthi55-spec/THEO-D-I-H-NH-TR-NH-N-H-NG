@echo off
chcp 65001 >nul
title Theo dõi hành trình đơn hàng

echo Đang khởi động ứng dụng Theo dõi hành trình đơn hàng...

if exist "%~dp0dist\Theo-doi-hanh-trinh-don-hang\Theo-doi-hanh-trinh-don-hang.exe" (
    start "" "%~dp0dist\Theo-doi-hanh-trinh-don-hang\Theo-doi-hanh-trinh-don-hang.exe"
    exit /b 0
)

if exist "%~dp0dist\Theo-doi-hanh-trinh-don-hang.exe" (
    start "" "%~dp0dist\Theo-doi-hanh-trinh-don-hang.exe"
    exit /b 0
)

py -3 "%~dp0run.py"
if %errorlevel% neq 0 (
    echo.
    echo Có lỗi khi khởi chạy ứng dụng!
    pause
)
