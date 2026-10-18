"""
Module tra cứu hành trình đơn hàng.
Hỗ trợ tra cứu SPX qua spx.vn/track và GHN qua donhang.ghn.vn.

Sử dụng Playwright để tự động hóa trình duyệt vì cả hai trang đều là SPA
(Single Page Application) không thể scrape bằng HTTP request đơn thuần.
"""

import asyncio
import re
import os
import sys
from datetime import datetime


def setup_playwright_environment():
    """Cấu hình để Playwright luôn tìm thấy trình duyệt đã cài đặt trên Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    ms_playwright = os.path.join(local_app_data, "ms-playwright") if local_app_data else ""
    if ms_playwright and os.path.exists(ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright


class TrackingResult:
    """Kết quả tra cứu vận đơn."""

    def __init__(self, success=False, status='', detail='', error=''):
        self.success = success
        self.status = status      # Trạng thái ngắn gọn
        self.detail = detail      # Chi tiết hành trình
        self.error = error        # Thông báo lỗi (nếu có)
        self.query_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


async def _track_spx_async(tracking_code):
    """Tra cứu đơn hàng SPX qua spx.vn/track."""
    setup_playwright_environment()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return TrackingResult(
            success=False,
            error="Chưa cài đặt Playwright. Hãy chạy: pip install playwright && playwright install chromium"
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale='vi-VN',
                viewport={'width': 1400, 'height': 900}
            )
            page = await context.new_page()

            # Truy cập trang tracking SPX (SPX nhận mã trực tiếp sau dấu ?, không dùng trackingNo=)
            await page.goto(
                f'https://spx.vn/track?{tracking_code}',
                timeout=30000,
                wait_until='domcontentloaded'
            )

            # Chờ trang load
            await page.wait_for_timeout(3000)

            # Đảm bảo ô input có đúng mã vận đơn thuần túy (không dính chữ thừa)
            try:
                inp = await page.query_selector('input')
                if inp:
                    current_val = await inp.input_value()
                    if current_val != tracking_code:
                        await inp.fill(tracking_code)

                # Bấm nút Theo dõi nếu có
                btn = await page.query_selector('button:has-text("Theo dõi"), .track-btn, button[type="submit"]')
                if btn:
                    await btn.click()
                else:
                    await page.keyboard.press('Enter')
                await page.wait_for_timeout(4000)
            except Exception:
                pass

            # Đọc toàn bộ văn bản trang để trích xuất hành trình
            body_text = await page.inner_text('body')
            lines = [l.strip() for l in body_text.split('\n') if l.strip()]

            # 1. Trích xuất các mốc hành trình dạng:
            # HH:MM:SS -> Ngày tháng -> Nội dung hành trình
            timeline_items = []
            i = 0
            while i < len(lines):
                if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', lines[i]):
                    t_str = lines[i]
                    d_str = lines[i+1] if i + 1 < len(lines) else ""
                    m_str = lines[i+2] if i + 2 < len(lines) else ""
                    if m_str and not re.match(r'^\d{1,2}:\d{2}', m_str) and not m_str.startswith('SPX'):
                        timeline_items.append({
                            'time': t_str,
                            'date': d_str,
                            'message': m_str
                        })
                        i += 3
                        continue
                i += 1

            status_text = ''
            detail_text = ''

            if timeline_items:
                # Trạng thái gần nhất chính là mốc đầu tiên
                status_text = timeline_items[0]['message']
                # Chi tiết đầy đủ
                detail_lines = [f"{it['time']} {it['date']}: {it['message']}" for it in timeline_items]
                detail_text = "\n".join(detail_lines)

            # 2. Nếu chưa có timeline_items, tìm trong các thẻ class message/text
            if not status_text:
                for sel in ['.message', 'p.text', '.status-text', '[class*="status"]', '[class*="message"]']:
                    try:
                        elements = await page.query_selector_all(sel)
                        for el in elements:
                            txt = (await el.inner_text()).strip()
                            if txt and len(txt) > 3 and not txt.startswith('SPX') and txt not in ['Theo dõi', 'Đăng nhập', 'Trang chủ']:
                                status_text = txt[:200]
                                detail_text = txt
                                break
                        if status_text:
                            break
                    except Exception:
                        pass

            # 3. Thử tìm qua 4 bước trạng thái chuẩn của SPX:
            if not status_text:
                stages = ['Đã giao hàng', 'Đang giao hàng', 'Đang vận chuyển', 'Chờ lấy hàng']
                for stage in stages:
                    if stage in lines:
                        status_text = stage
                        detail_text = f"Trạng thái: {stage}"
                        break

            await browser.close()

            if status_text:
                return TrackingResult(
                    success=True,
                    status=status_text,
                    detail=detail_text.strip()[:2000] if detail_text else status_text
                )
            else:
                # Chỉ báo không tìm thấy nếu không có bất kỳ trạng thái nào
                return TrackingResult(
                    success=False,
                    error=f"Không tìm thấy hành trình cho mã {tracking_code}. "
                          f"Vui lòng tra cứu tại: https://spx.vn/track?{tracking_code}"
                )

    except Exception as e:
        error_msg = str(e)
        if 'Timeout' in error_msg or 'timeout' in error_msg:
            return TrackingResult(
                success=False,
                error=f"Hết thời gian chờ khi tra cứu {tracking_code}. Vui lòng thử lại."
            )
        elif 'net::' in error_msg:
            return TrackingResult(
                success=False,
                error=f"Lỗi kết nối mạng khi tra cứu {tracking_code}. Kiểm tra kết nối Internet."
            )
        else:
            return TrackingResult(
                success=False,
                error=f"Lỗi tra cứu SPX {tracking_code}: {error_msg[:200]}"
            )


async def _track_ghn_async(tracking_code, phone_last4=''):
    """Tra cứu đơn hàng GHN qua donhang.ghn.vn."""
    setup_playwright_environment()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return TrackingResult(
            success=False,
            error="Chưa cài đặt Playwright. Hãy chạy: pip install playwright && playwright install chromium"
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale='vi-VN',
                viewport={'width': 1400, 'height': 900}
            )
            page = await context.new_page()

            # Truy cập trang tracking GHN
            url = f'https://donhang.ghn.vn/?order_code={tracking_code}'
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # Chờ trang load
            await page.wait_for_timeout(3000)

            # Trang GHN có 2 ô: 1 là mã đơn hàng, 2 là số điện thoại
            inputs = await page.query_selector_all('input')
            if len(inputs) > 0:
                val0 = await inputs[0].input_value()
                if not val0:
                    await inputs[0].fill(tracking_code)

            if len(inputs) > 1:
                if phone_last4:
                    await inputs[1].fill(phone_last4)
                    btn = await page.query_selector('button:has-text("Tra cứu"), button[type="submit"]')
                    if btn:
                        await btn.click()
                    else:
                        await page.keyboard.press('Enter')
                    await page.wait_for_timeout(4000)
                else:
                    await browser.close()
                    return TrackingResult(
                        success=False,
                        error=f"Trang Giao Hàng Nhanh bắt buộc cần Số điện thoại hoặc 4 số cuối SĐT để tra cứu {tracking_code}."
                    )
            else:
                # Nếu trang chỉ có 1 ô hoặc đã tự tra cứu
                btn = await page.query_selector('button:has-text("Tra cứu"), button[type="submit"]')
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(4000)

            # Kiểm tra các thông báo lỗi từ GHN
            body_text = await page.inner_text('body')
            body_lower = body_text.lower()

            if 'thông tin không chính xác' in body_lower:
                await browser.close()
                return TrackingResult(
                    success=False,
                    error=f"Số điện thoại ({phone_last4}) không khớp với đơn hàng GHN {tracking_code}. Vui lòng kiểm tra lại SĐT người nhận/người gửi."
                )

            if 'vui lòng nhập số điện thoại' in body_lower:
                await browser.close()
                return TrackingResult(
                    success=False,
                    error=f"Trang GHN yêu cầu Số điện thoại hoặc 4 số cuối SĐT để tra cứu {tracking_code}."
                )

            not_found_indicators = [
                'không tìm thấy đơn hàng', 'đơn hàng không tồn tại',
                'mã đơn hàng không hợp lệ'
            ]
            for indicator in not_found_indicators:
                if indicator in body_lower:
                    await browser.close()
                    return TrackingResult(
                        success=False,
                        error=f"Không tìm thấy đơn hàng GHN với mã {tracking_code}"
                    )

            status_text = ''
            detail_text = ''

            # Trích xuất hành trình chi tiết từ văn bản trang GHN
            body_text = await page.inner_text('body')
            lines = [l.strip() for l in body_text.split('\n') if l.strip()]

            # 1. Tìm phần timeline sau "Hành trình đơn hàng"
            start_idx = 0
            for idx, line in enumerate(lines):
                if 'hành trình đơn hàng' in line.lower():
                    start_idx = idx + 1
                    break

            timeline_items = []
            stages = ['tạo đơn', 'đang lấy hàng', 'đang vận chuyển', 'đang giao hàng', 'giao hàng thành công', 'chuyển hoàn']

            i = start_idx
            while i < len(lines):
                line = lines[i]
                if 'lịch sử liên hệ' in line.lower():
                    break
                if line.startswith('Cập nhật'):
                    i += 1
                    continue

                if re.match(r'^\d{1,2}:\d{2}$', line):
                    t_str = line
                    d_str = lines[i+1] if i + 1 < len(lines) else ""
                    m_str = lines[i+2] if i + 2 < len(lines) else ""
                    advance = 3
                    if m_str.lower() in stages:
                        detail_msg = lines[i+3] if i + 3 < len(lines) else ""
                        if detail_msg and not re.match(r'^\d{1,2}:\d{2}$', detail_msg):
                            m_str = detail_msg
                            advance = 4

                    if m_str and 'lịch sử liên hệ' not in m_str.lower():
                        timeline_items.append({
                            'time': t_str,
                            'date': d_str,
                            'message': m_str
                        })
                    i += advance
                    continue
                i += 1

            if timeline_items:
                # Trạng thái gần nhất chính là mốc mới nhất ở đầu danh sách hành trình
                status_text = timeline_items[0]['message']
                detail_text = "\n".join([f"{it['time']} {it['date']}: {it['message']}" for it in timeline_items])

            # 2. Nếu timeline chưa có mốc giờ, lấy thông tin tóm tắt giữa stepper và Thông tin đơn hàng
            if not status_text:
                summary_lines = []
                collecting = False
                for line in lines:
                    if 'đang giao hàng' in line.lower():
                        collecting = True
                        continue
                    if 'thông tin đơn hàng' in line.lower():
                        break
                    if collecting and line and len(line) > 3:
                        if not line.startswith('Dự kiến') and not line.startswith('Tra cứu'):
                            summary_lines.append(line)
                if summary_lines:
                    status_text = summary_lines[0][:200]
                    detail_text = "\n".join(summary_lines)

            # 3. Fallback: tìm qua selector
            if not status_text:
                for selector in ['.order-status', '.status', '[class*="status"]', '.order-info']:
                    try:
                        elements = await page.query_selector_all(selector)
                        for el in elements:
                            text = (await el.inner_text()).strip()
                            if text and len(text) > 2 and text.lower() not in stages:
                                status_text = text[:200]
                                detail_text = text
                                break
                        if status_text:
                            break
                    except Exception:
                        pass

            await browser.close()

            if status_text:
                return TrackingResult(
                    success=True,
                    status=status_text,
                    detail=detail_text.strip()[:2000] if detail_text else status_text
                )
            else:
                return TrackingResult(
                    success=False,
                    error=f"Không thể đọc trạng thái đơn hàng GHN {tracking_code}. "
                          f"Vui lòng tra cứu thủ công tại: https://donhang.ghn.vn/?order_code={tracking_code}"
                )

    except Exception as e:
        error_msg = str(e)
        if 'Timeout' in error_msg or 'timeout' in error_msg:
            return TrackingResult(
                success=False,
                error=f"Hết thời gian chờ khi tra cứu GHN {tracking_code}. Vui lòng thử lại."
            )
        elif 'net::' in error_msg:
            return TrackingResult(
                success=False,
                error=f"Lỗi kết nối mạng khi tra cứu GHN {tracking_code}. Kiểm tra kết nối Internet."
            )
        else:
            return TrackingResult(
                success=False,
                error=f"Lỗi tra cứu GHN {tracking_code}: {error_msg[:200]}"
            )


def track_spx(tracking_code):
    """Tra cứu đơn SPX (synchronous wrapper)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Nếu đang trong event loop (ví dụ: Qt), tạo task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _track_spx_async(tracking_code))
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(_track_spx_async(tracking_code))
    except RuntimeError:
        return asyncio.run(_track_spx_async(tracking_code))


def track_ghn(tracking_code, phone_last4=''):
    """Tra cứu đơn GHN (synchronous wrapper)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, _track_ghn_async(tracking_code, phone_last4)
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(
                _track_ghn_async(tracking_code, phone_last4)
            )
    except RuntimeError:
        return asyncio.run(_track_ghn_async(tracking_code, phone_last4))


def track_order(tracking_code, carrier, phone_last4=''):
    """
    Tra cứu đơn hàng dựa trên mã vận đơn và đơn vị vận chuyển.
    
    Args:
        tracking_code: Mã vận đơn
        carrier: Đơn vị vận chuyển (SPX/GHN)
        phone_last4: 4 số cuối SĐT (chỉ cho GHN)
    
    Returns:
        TrackingResult
    """
    from .carrier import CARRIER_SPX, CARRIER_GHN

    if not tracking_code or not tracking_code.strip():
        return TrackingResult(
            success=False,
            error="Mã vận đơn trống"
        )

    if carrier == CARRIER_SPX:
        return track_spx(tracking_code.strip())
    elif carrier == CARRIER_GHN:
        return track_ghn(tracking_code.strip(), phone_last4)
    else:
        return TrackingResult(
            success=False,
            error=f"Chưa xác định đơn vị vận chuyển cho mã {tracking_code}. "
                  f"Vui lòng chọn đơn vị vận chuyển (SPX hoặc GHN) cho đơn hàng này."
        )


def open_tracking_url(tracking_code, carrier):
    """Mở trang tra cứu trong trình duyệt mặc định."""
    import webbrowser
    from .carrier import CARRIER_SPX, CARRIER_GHN

    # Tự động sao chép mã vận đơn vào Clipboard để người dùng dán nếu cần
    try:
        from PySide6.QtGui import QGuiApplication
        clip = QGuiApplication.clipboard()
        if clip:
            clip.setText(tracking_code)
    except Exception:
        pass

    if carrier == CARRIER_SPX:
        # SPX nhận mã trực tiếp sau dấu ? (VD: https://spx.vn/track?SPXVN...)
        url = f'https://spx.vn/track?{tracking_code}'
    elif carrier == CARRIER_GHN:
        url = f'https://donhang.ghn.vn/?order_code={tracking_code}'
    else:
        return False

    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False
