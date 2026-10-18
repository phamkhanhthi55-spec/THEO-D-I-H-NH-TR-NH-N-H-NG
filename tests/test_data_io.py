"""
Kiểm thử chức năng nhập/xuất Excel và CSV.
"""

import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_io import export_excel, export_csv, import_excel, import_csv, import_file, parse_amount, format_amount


class TestExcelCSV(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_export_import_csv(self):
        csv_path = os.path.join(self.temp_dir, "test_orders.csv")
        sample_orders = [
            {
                'account_name': 'Acc_Shopee_01',
                'product_name': 'Chuột không dây Logitech',
                'tracking_code': 'SPXVN012345678',
                'journey_status': 'Đang trung chuyển',
                'amount': 250000.0,
                'amount_text': '250.000 ₫'
            },
            {
                'account_name': 'Acc_Lazada_02',
                'product_name': 'Bàn phím cơ DareU',
                'tracking_code': 'GHN99887766',
                'journey_status': 'Đã giao thành công',
                'amount': 650000.0,
                'amount_text': '650.000 ₫'
            }
        ]
        export_csv(csv_path, sample_orders)
        self.assertTrue(os.path.exists(csv_path))

        imported_orders, warnings = import_csv(csv_path)
        self.assertEqual(len(imported_orders), 2)
        self.assertEqual(imported_orders[0]['account_name'], 'Acc_Shopee_01')
        self.assertEqual(imported_orders[0]['product_name'], 'Chuột không dây Logitech')
        self.assertEqual(imported_orders[0]['tracking_code'], 'SPXVN012345678')
        self.assertEqual(imported_orders[0]['journey_status'], 'Đang trung chuyển')
        self.assertEqual(imported_orders[0]['amount'], 250000.0)

        self.assertEqual(imported_orders[1]['account_name'], 'Acc_Lazada_02')
        self.assertEqual(imported_orders[1]['product_name'], 'Bàn phím cơ DareU')
        self.assertEqual(imported_orders[1]['tracking_code'], 'GHN99887766')
        self.assertEqual(imported_orders[1]['journey_status'], 'Đã giao thành công')
        self.assertEqual(imported_orders[1]['amount'], 650000.0)

    def test_export_import_excel(self):
        xlsx_path = os.path.join(self.temp_dir, "test_orders.xlsx")
        sample_orders = [
            {
                'account_name': 'Acc_Shopee_VN',
                'product_name': 'Tai nghe Bluetooth Pro',
                'tracking_code': 'SPXVN987654321',
                'journey_status': 'Đang giao hàng',
                'amount': 450000.0,
                'amount_text': '450.000 ₫'
            }
        ]
        export_excel(xlsx_path, sample_orders)
        self.assertTrue(os.path.exists(xlsx_path))

        imported_orders, warnings = import_excel(xlsx_path)
        self.assertEqual(len(imported_orders), 1)
        self.assertEqual(imported_orders[0]['account_name'], 'Acc_Shopee_VN')
        self.assertEqual(imported_orders[0]['product_name'], 'Tai nghe Bluetooth Pro')
        self.assertEqual(imported_orders[0]['tracking_code'], 'SPXVN987654321')
        self.assertEqual(imported_orders[0]['journey_status'], 'Đang giao hàng')
        self.assertEqual(imported_orders[0]['amount'], 450000.0)

    def test_import_file_dispatcher(self):
        csv_path = os.path.join(self.temp_dir, "auto.csv")
        export_csv(csv_path, [{'account_name': 'Test', 'product_name': 'SP', 'tracking_code': 'C1', 'journey_status': 'OK', 'amount': 1000, 'amount_text': '1.000'}])
        orders, _ = import_file(csv_path)
        self.assertEqual(len(orders), 1)


if __name__ == '__main__':
    unittest.main()
