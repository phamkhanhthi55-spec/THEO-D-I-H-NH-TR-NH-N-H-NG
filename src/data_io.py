"""
Module nhập/xuất dữ liệu Excel (.xlsx) và CSV.
Đảm bảo giữ nguyên tiếng Việt và giá trị số tiền.
"""

import csv
import os
import re
from datetime import datetime


def parse_amount(text):
    """
    Phân tích chuỗi số tiền thành giá trị số.
    Hỗ trợ các định dạng: 250000, 250.000, 250,000, 250.000 ₫, etc.
    """
    if isinstance(text, (int, float)):
        return float(text)

    if not text or not str(text).strip():
        return 0

    text = str(text).strip()
    # Loại bỏ ký hiệu tiền tệ và khoảng trắng
    text = text.replace('₫', '').replace('đ', '').replace('VND', '')
    text = text.replace('VNĐ', '').strip()

    # Xử lý dấu phân cách hàng nghìn (dấu chấm trong VN)
    # Pattern: 250.000 hoặc 1.250.000
    if re.match(r'^\d{1,3}(\.\d{3})+$', text):
        text = text.replace('.', '')
    # Pattern: 250,000
    elif re.match(r'^\d{1,3}(,\d{3})+$', text):
        text = text.replace(',', '')

    try:
        return float(text)
    except ValueError:
        return 0


def format_amount(value):
    """Định dạng số tiền theo kiểu Việt Nam: 250.000 ₫"""
    if value is None or value == 0:
        return ''
    try:
        val = float(value)
        if val == int(val):
            formatted = f"{int(val):,}".replace(',', '.')
        else:
            formatted = f"{val:,.0f}".replace(',', '.')
        return f"{formatted} ₫"
    except (ValueError, TypeError):
        return str(value)


def import_excel(file_path):
    """
    Nhập dữ liệu từ file Excel (.xlsx).

    Returns:
        (list[dict], list[str]): Danh sách đơn hàng và danh sách cảnh báo
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Cần cài đặt openpyxl: pip install openpyxl")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    orders = []
    warnings = []

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        # Đọc header để xác định cột
        header_map = {}
        header_aliases = {
            'tên acc đặt': 'account_name',
            'tên acc': 'account_name',
            'acc': 'account_name',
            'account': 'account_name',
            'tên sp': 'product_name',
            'sản phẩm': 'product_name',
            'product': 'product_name',
            'mã vận đơn': 'tracking_code',
            'vận đơn': 'tracking_code',
            'tracking': 'tracking_code',
            'tracking code': 'tracking_code',
            'hành trình di chuyển': 'journey_status',
            'hành trình': 'journey_status',
            'trạng thái': 'journey_status',
            'status': 'journey_status',
            'money': 'amount_text',
            'số tiền cần thanh toán': 'amount_text',
            'số tiền': 'amount_text',
            'tiền': 'amount_text',
            'amount': 'amount_text',
            'thanh toán': 'amount_text',
            'địa chỉ': 'address',
            'dia chi': 'address',
            'diachi': 'address',
            'address': 'address',
        }

        first_row = None
        for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
            first_row = row
            break

        if first_row:
            for idx, cell_value in enumerate(first_row):
                if cell_value:
                    key = str(cell_value).strip().lower()
                    if key in header_aliases:
                        header_map[idx] = header_aliases[key]
                    elif key == 'stt' or key == '#':
                        continue  # Bỏ qua cột STT

        # Nếu không có header, dùng thứ tự mặc định (bỏ cột STT)
        if not header_map:
            # Giả sử thứ tự: STT, Tên acc, Tên SP, Mã vận đơn, Hành trình, Số tiền, Địa chỉ
            default_cols = [
                (1, 'account_name'),
                (2, 'product_name'),
                (3, 'tracking_code'),
                (4, 'journey_status'),
                (5, 'amount_text'),
                (6, 'address'),
            ]
            for idx, field in default_cols:
                if first_row and idx < len(first_row):
                    header_map[idx] = field
            warnings.append("Không nhận diện được tiêu đề cột. Sử dụng thứ tự mặc định.")
            start_row = 1  # Bắt đầu từ dòng đầu vì không có header
        else:
            start_row = 2  # Bỏ qua dòng header

        row_num = 0
        for row in ws.iter_rows(min_row=start_row, values_only=True):
            row_num += 1
            # Kiểm tra dòng trống
            if all(cell is None or str(cell).strip() == '' for cell in row):
                continue

            order = {
                'account_name': '',
                'product_name': '',
                'tracking_code': '',
                'journey_status': '',
                'amount': 0,
                'amount_text': '',
                'address': '',
            }

            for idx, field in header_map.items():
                if idx < len(row) and row[idx] is not None:
                    value = str(row[idx]).strip()
                    if field == 'amount_text':
                        order['amount_text'] = value
                        order['amount'] = parse_amount(value)
                    else:
                        order[field] = value

            orders.append(order)

        wb.close()

    except Exception as e:
        raise RuntimeError(f"Lỗi đọc file Excel: {e}")

    return orders, warnings


def import_csv(file_path):
    """
    Nhập dữ liệu từ file CSV.

    Returns:
        (list[dict], list[str]): Danh sách đơn hàng và danh sách cảnh báo
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    orders = []
    warnings = []

    # Thử các encoding phổ biến
    encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                # Detect delimiter
                sample = f.read(8192)
                f.seek(0)

                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample)
                except csv.Error:
                    dialect = csv.excel

                reader = csv.reader(f, dialect)
                rows = list(reader)
                if rows:
                    break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise RuntimeError("Không thể đọc file CSV. Kiểm tra encoding.")

    if not rows:
        return [], ["File CSV trống"]

    # Xử lý header
    header_aliases = {
        'tên acc đặt': 'account_name',
        'tên acc': 'account_name',
        'acc': 'account_name',
        'account': 'account_name',
        'tên sp': 'product_name',
        'sản phẩm': 'product_name',
        'product': 'product_name',
        'mã vận đơn': 'tracking_code',
        'vận đơn': 'tracking_code',
        'tracking': 'tracking_code',
        'tracking code': 'tracking_code',
        'hành trình di chuyển': 'journey_status',
        'hành trình': 'journey_status',
        'trạng thái': 'journey_status',
        'status': 'journey_status',
        'money': 'amount_text',
        'số tiền cần thanh toán': 'amount_text',
        'số tiền': 'amount_text',
        'tiền': 'amount_text',
        'amount': 'amount_text',
        'thanh toán': 'amount_text',
        'địa chỉ': 'address',
        'dia chi': 'address',
        'diachi': 'address',
        'address': 'address',
    }

    header_map = {}
    first_row = rows[0]

    for idx, cell in enumerate(first_row):
        key = cell.strip().lower()
        if key in header_aliases:
            header_map[idx] = header_aliases[key]
        elif key == 'stt' or key == '#':
            continue

    if header_map:
        data_rows = rows[1:]
    else:
        default_cols = [
            (1, 'account_name'),
            (2, 'product_name'),
            (3, 'tracking_code'),
            (4, 'journey_status'),
            (5, 'amount_text'),
            (6, 'address'),
        ]
        for idx, field in default_cols:
            header_map[idx] = field
        data_rows = rows
        warnings.append("Không nhận diện được tiêu đề cột. Sử dụng thứ tự mặc định.")

    for row in data_rows:
        if all(not cell.strip() for cell in row):
            continue

        order = {
            'account_name': '',
            'product_name': '',
            'tracking_code': '',
            'journey_status': '',
            'amount': 0,
            'amount_text': '',
            'address': '',
        }

        for idx, field in header_map.items():
            if idx < len(row):
                value = row[idx].strip()
                if field == 'amount_text':
                    order['amount_text'] = value
                    order['amount'] = parse_amount(value)
                else:
                    order[field] = value

        orders.append(order)

    return orders, warnings


def export_excel(file_path, orders, custom_columns=None):
    """
    Xuất dữ liệu ra file Excel (.xlsx).
    Giữ đúng thứ tự: STT, Tên acc đặt, Tên SP, Mã vận đơn,
    Hành trình di chuyển, Số tiền cần thanh toán, Địa chỉ và các cột tùy chọn.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        raise ImportError("Cần cài đặt openpyxl: pip install openpyxl")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Đơn hàng"

    custom_cols = list(custom_columns or [])
    headers = ['STT', 'Tên acc đặt', 'Tên SP', 'Mã vận đơn',
               'Hành trình di chuyển', 'Money', 'Địa chỉ'] + custom_cols

    header_fill = PatternFill(start_color='FF7891', end_color='FF7891', fill_type='solid')
    header_font_white = Font(bold=True, size=11, color='FFFFFF')
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    # Data
    for row_idx, order in enumerate(orders, 2):
        stt = row_idx - 1
        ws.cell(row=row_idx, column=1, value=stt).border = thin_border
        ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal='center')

        ws.cell(row=row_idx, column=2,
                value=order.get('account_name', '')).border = thin_border
        ws.cell(row=row_idx, column=3,
                value=order.get('product_name', '')).border = thin_border
        ws.cell(row=row_idx, column=4,
                value=order.get('tracking_code', '')).border = thin_border
        ws.cell(row=row_idx, column=5,
                value=order.get('journey_status', '')).border = thin_border

        # Số tiền: giữ nguyên giá trị người dùng đã nhập
        amount_text = order.get('amount_text', '')
        if not amount_text:
            amount = order.get('amount', 0)
            if amount and amount > 0:
                amount_text = format_amount(amount)

        ws.cell(row=row_idx, column=6, value=amount_text).border = thin_border

        # Cột 7: Địa chỉ
        ws.cell(row=row_idx, column=7,
                value=order.get('address', '')).border = thin_border

        # Cột tùy chọn
        extra = order.get('extra_data') or '{}'
        if isinstance(extra, str):
            try:
                import json
                extra_dict = json.loads(extra)
            except Exception:
                extra_dict = {}
        else:
            extra_dict = extra or {}

        for c_idx, c_name in enumerate(custom_cols, 8):
            ws.cell(row=row_idx, column=c_idx,
                    value=extra_dict.get(c_name, '')).border = thin_border

    # Điều chỉnh chiều rộng cột
    ws.column_dimensions['A'].width = 6    # STT
    ws.column_dimensions['B'].width = 20   # Tên acc đặt
    ws.column_dimensions['C'].width = 30   # Tên SP
    ws.column_dimensions['D'].width = 22   # Mã vận đơn
    ws.column_dimensions['E'].width = 40   # Hành trình
    ws.column_dimensions['F'].width = 25   # Số tiền
    ws.column_dimensions['G'].width = 18   # Địa chỉ

    try:
        wb.save(file_path)
    except PermissionError:
        raise RuntimeError(f"Không thể lưu file. File có thể đang được mở: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Lỗi xuất file Excel: {e}")


def export_csv(file_path, orders, custom_columns=None):
    """
    Xuất dữ liệu ra file CSV với encoding UTF-8 BOM.
    """
    custom_cols = list(custom_columns or [])
    headers = ['STT', 'Tên acc đặt', 'Tên SP', 'Mã vận đơn',
               'Hành trình di chuyển', 'Money', 'Địa chỉ'] + custom_cols

    try:
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for idx, order in enumerate(orders, 1):
                amount_text = order.get('amount_text', '')
                if not amount_text:
                    amount = order.get('amount', 0)
                    if amount and amount > 0:
                        amount_text = format_amount(amount)

                extra = order.get('extra_data') or '{}'
                if isinstance(extra, str):
                    try:
                        import json
                        extra_dict = json.loads(extra)
                    except Exception:
                        extra_dict = {}
                else:
                    extra_dict = extra or {}

                row_vals = [
                    idx,
                    order.get('account_name', ''),
                    order.get('product_name', ''),
                    order.get('tracking_code', ''),
                    order.get('journey_status', ''),
                    amount_text,
                    order.get('address', ''),
                ] + [extra_dict.get(c, '') for c in custom_cols]

                writer.writerow(row_vals)
    except PermissionError:
        raise RuntimeError(f"Không thể lưu file. File có thể đang được mở: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Lỗi xuất file CSV: {e}")


def import_file(file_path):
    """
    Nhập dữ liệu từ file Excel hoặc CSV tùy theo phần mở rộng.

    Returns:
        (list[dict], list[str]): Danh sách đơn hàng và cảnh báo
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.xlsx':
        return import_excel(file_path)
    elif ext == '.csv':
        return import_csv(file_path)
    elif ext == '.xls':
        raise RuntimeError("Không hỗ trợ file .xls cũ. Vui lòng chuyển sang .xlsx")
    else:
        raise RuntimeError(f"Định dạng file không được hỗ trợ: {ext}")
