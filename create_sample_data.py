"""
Tạo dữ liệu mẫu Excel và CSV để người dùng thử nghiệm nhập vào ứng dụng.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_io import export_excel, export_csv

sample_orders = [
    {
        'account_name': 'Shop_PhuKien_VN',
        'product_name': 'Cáp sạc Type-C nhanh 65W',
        'tracking_code': 'SPXVN045812938472',
        'journey_status': 'Đang vận chuyển đến bưu cục',
        'amount': 120000,
        'amount_text': '120.000 ₫'
    },
    {
        'account_name': 'ThietBiSo_Store',
        'product_name': 'Bàn phím cơ không dây Bluetooth',
        'tracking_code': 'SPXVN098172635410',
        'journey_status': 'Đã giao hàng thành công',
        'amount': 750000,
        'amount_text': '750.000 ₫'
    },
    {
        'account_name': 'GiaDung_ThongMinh',
        'product_name': 'Nồi chiên không dầu 5.5L',
        'tracking_code': 'GHN99283716',
        'journey_status': 'Đang giao hàng',
        'amount': 1250000,
        'amount_text': '1.250.000 ₫'
    },
    {
        'account_name': 'MyPham_ChinhHang',
        'product_name': 'Kem chống nắng nâng tone 50ml',
        'tracking_code': 'GHN77162534',
        'journey_status': 'Chờ lấy hàng',
        'amount': 320000,
        'amount_text': '320.000 ₫'
    },
    {
        'account_name': 'ThoiTrang_NamNu',
        'product_name': 'Áo hoodie unisex nỉ bông',
        'tracking_code': 'SPXVN019283746523',
        'journey_status': '',
        'amount': 290000,
        'amount_text': '290.000 ₫'
    }
]

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

xlsx_path = os.path.join(data_dir, 'mau_don_hang.xlsx')
csv_path = os.path.join(data_dir, 'mau_don_hang.csv')

export_excel(xlsx_path, sample_orders)
export_csv(csv_path, sample_orders)

print(f"Da tao mau Excel: {xlsx_path}")
print(f"Da tao mau CSV: {csv_path}")
