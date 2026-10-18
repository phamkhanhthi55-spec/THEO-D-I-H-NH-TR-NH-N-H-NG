"""
Module nhận diện đơn vị vận chuyển dựa trên mã vận đơn.
Hỗ trợ: Shopee Express (SPX) và Giao Hàng Nhanh (GHN).

Định dạng mã vận đơn đã xác minh:
- SPX: Bắt đầu bằng "SPXVN" hoặc "SPX", theo sau bởi các chữ số.
  Ví dụ: SPXVN012345678901, SPX012345678
- GHN: Thường có dạng mã chữ + số do hệ thống GHN sinh ra.
  Ví dụ: GHN2A1B3C, LJKVNG0123456789
  Lưu ý: Không phải tất cả mã bắt đầu bằng "G" đều là GHN.
"""

import re

# Carrier identifiers
CARRIER_SPX = 'SPX'
CARRIER_GHN = 'GHN'
CARRIER_UNKNOWN = ''

# Regex patterns
SPX_PATTERN = re.compile(r'^SPX(VN)?\d{6,}$', re.IGNORECASE)


def detect_carrier(tracking_code):
    """
    Nhận diện đơn vị vận chuyển từ mã vận đơn.

    Returns:
        str: CARRIER_SPX, CARRIER_GHN hoặc CARRIER_UNKNOWN
    """
    if not tracking_code or not tracking_code.strip():
        return CARRIER_UNKNOWN

    code = tracking_code.strip().upper()

    # SPX: mã bắt đầu bằng SPX hoặc SPXVN
    if code.startswith('SPX') or SPX_PATTERN.match(code):
        return CARRIER_SPX

    # GHN: Mã GHN bắt đầu bằng G (như GYMUKCCG, GYH6PZDC, G...), GHN, hoặc LJK
    if code.startswith('GHN') or code.startswith('G') or code.startswith('LJK'):
        return CARRIER_GHN

    return CARRIER_UNKNOWN


def get_carrier_name(carrier_code):
    """Trả về tên đầy đủ của đơn vị vận chuyển."""
    names = {
        CARRIER_SPX: 'Shopee Express (SPX)',
        CARRIER_GHN: 'Giao Hàng Nhanh (GHN)',
        CARRIER_UNKNOWN: 'Chưa xác định',
    }
    return names.get(carrier_code, 'Chưa xác định')


def validate_tracking_code(tracking_code):
    """
    Kiểm tra tính hợp lệ cơ bản của mã vận đơn.
    Returns: (is_valid: bool, message: str)
    """
    if not tracking_code or not tracking_code.strip():
        return False, "Mã vận đơn không được để trống"

    code = tracking_code.strip()
    if len(code) < 5:
        return False, "Mã vận đơn quá ngắn"
    if len(code) > 30:
        return False, "Mã vận đơn quá dài"
    if not re.match(r'^[A-Za-z0-9]+$', code):
        return False, "Mã vận đơn chỉ được chứa chữ cái và số"

    return True, ""


def needs_phone_last4(carrier_code):
    """Kiểm tra xem đơn vị vận chuyển có yêu cầu 4 số cuối điện thoại không."""
    return carrier_code == CARRIER_GHN
