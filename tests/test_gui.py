"""
Kiểm thử giao diện đồ họa (GUI) ở chế độ offscreen/headless.
Đảm bảo các thao tác thêm, sửa, xóa, tìm kiếm, lọc, hiển thị đúng 6 cột không gây lỗi.
"""

import sys
import os
import tempfile
import unittest

# Set offscreen platform for Qt headless test
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from src.database import DatabaseManager
from src.main_window import MainWindow, OrderDialog


class TestGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create single QApplication instance
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "gui_test.db")
        # Instantiate MainWindow
        self.window = MainWindow()
        # Point to test db
        self.window.db.close()
        self.window.db = DatabaseManager(self.db_path)
        self.window.load_data()

    def tearDown(self):
        self.window.db.close()
        self.window.close()

    def test_window_initialization(self):
        """Kiểm tra khởi tạo giao diện và số cột."""
        self.assertEqual(self.window.table.columnCount(), 7)
        expected_headers = ['STT', 'Tên acc đặt', 'Tên SP', 'Mã vận đơn',
                            'Hành trình di chuyển', 'Số tiền cần thanh toán', 'Địa chỉ']
        for i, header in enumerate(expected_headers):
            self.assertEqual(self.window.table.horizontalHeaderItem(i).text(), header)

    def test_add_and_display_order(self):
        """Kiểm tra thêm đơn hàng và cập nhật hiển thị bảng."""
        self.window.db.add_order(
            account_name="User_Shopee_01",
            product_name="Áo thun polo nam",
            tracking_code="SPXVN012345678901",
            carrier="SPX",
            amount=199000,
            amount_text="199.000 ₫",
            address="Bình Định"
        )
        self.window.load_data()

        self.assertEqual(self.window.table.rowCount(), 1)
        # Kiểm tra thứ tự và giá trị cột
        self.assertEqual(self.window.table.item(0, 0).text(), "1") # STT
        self.assertEqual(self.window.table.item(0, 1).text(), "User_Shopee_01") # Tên acc
        self.assertEqual(self.window.table.item(0, 2).text(), "Áo thun polo nam") # Tên SP
        self.assertEqual(self.window.table.item(0, 3).text(), "SPXVN012345678901") # Mã vận đơn
        self.assertEqual(self.window.table.item(0, 4).text(), "") # Hành trình
        self.assertEqual(self.window.table.item(0, 5).text(), "199.000 ₫") # Số tiền
        # Cột 6: Địa chỉ (QComboBox widget)
        addr_combo = self.window.table.cellWidget(0, 6)
        self.assertIsNotNone(addr_combo)
        self.assertEqual(addr_combo.currentText(), "Bình Định")

    def test_search_and_filter(self):
        """Kiểm tra tìm kiếm và lọc dữ liệu trên giao diện."""
        self.window.db.add_order(account_name="Alice", product_name="Váy hoa", tracking_code="SPXVN111", carrier="SPX")
        self.window.db.add_order(account_name="Bob", product_name="Quần jean", tracking_code="GHN222", carrier="GHN")
        self.window.load_data()
        self.assertEqual(self.window.table.rowCount(), 2)

        # Tìm kiếm Alice
        self.window.search_edit.setText("Alice")
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.window.table.item(0, 1).text(), "Alice")

        # Xóa tìm kiếm
        self.window.search_edit.setText("")
        self.assertEqual(self.window.table.rowCount(), 2)

    def test_sorting_keeps_stt_sequential(self):
        """Kiểm tra khi sắp xếp theo bất kỳ cột nào, STT luôn từ 1 đến N liên tục."""
        self.window.db.add_order(account_name="Charlie", product_name="Zebra Product", tracking_code="SPXVN333", carrier="SPX")
        self.window.db.add_order(account_name="Alice", product_name="Apple Product", tracking_code="SPXVN111", carrier="SPX")
        self.window.db.add_order(account_name="Bob", product_name="Banana Product", tracking_code="SPXVN222", carrier="SPX")
        self.window.load_data()
        self.assertEqual(self.window.table.rowCount(), 3)

        # 1. Sắp xếp theo Tên SP (cột 2) tăng dần -> Apple, Banana, Zebra
        self.window._on_header_section_clicked(2)
        self.assertEqual(self.window.table.item(0, 2).text(), "Apple Product")
        self.assertEqual(self.window.table.item(1, 2).text(), "Banana Product")
        self.assertEqual(self.window.table.item(2, 2).text(), "Zebra Product")
        # STT phải luôn là 1, 2, 3
        self.assertEqual(self.window.table.item(0, 0).text(), "1")
        self.assertEqual(self.window.table.item(1, 0).text(), "2")
        self.assertEqual(self.window.table.item(2, 0).text(), "3")

        # 2. Sắp xếp theo Tên SP (cột 2) giảm dần -> Zebra, Banana, Apple
        self.window._on_header_section_clicked(2)
        self.assertEqual(self.window.table.item(0, 2).text(), "Zebra Product")
        self.assertEqual(self.window.table.item(1, 2).text(), "Banana Product")
        self.assertEqual(self.window.table.item(2, 2).text(), "Apple Product")
        # STT vẫn phải giữ nguyên 1, 2, 3
        self.assertEqual(self.window.table.item(0, 0).text(), "1")
        self.assertEqual(self.window.table.item(1, 0).text(), "2")
        self.assertEqual(self.window.table.item(2, 0).text(), "3")

    def test_delivery_status_priority_ordering(self):
        """Kiểm tra:
        - Đơn thông thường ở trên cùng.
        - Đơn 'đang giao hàng' bị đẩy xuống kề cuối.
        - Đơn 'giao hàng thành công' bị đẩy xuống cuối cùng.
        - STT vẫn liên tục 1, 2, 3, 4.
        """
        id1 = self.window.db.add_order(account_name="Acc1", product_name="Đơn giao xong", tracking_code="SPX01", carrier="SPX")
        self.window.db.update_journey(id1, "Giao hàng thành công", "Đã giao cho khách")

        id2 = self.window.db.add_order(account_name="Acc2", product_name="Đơn đang đi", tracking_code="SPX02", carrier="SPX")
        self.window.db.update_journey(id2, "Đang trung chuyển", "Kho phân loại")

        id3 = self.window.db.add_order(account_name="Acc3", product_name="Đơn đang ship", tracking_code="SPX03", carrier="SPX")
        self.window.db.update_journey(id3, "Đang giao hàng", "Shipper đang giao")

        id4 = self.window.db.add_order(account_name="Acc4", product_name="Đơn mới", tracking_code="SPX04", carrier="SPX")

        self.window.load_data()
        self.assertEqual(self.window.table.rowCount(), 4)

        # 2 đơn thông thường phải ở 2 hàng đầu (row 0, 1)
        first_two = [self.window.table.item(0, 2).text(), self.window.table.item(1, 2).text()]
        self.assertIn("Đơn đang đi", first_two)
        self.assertIn("Đơn mới", first_two)

        # Hàng kề cuối (row 2) phải là 'Đang giao hàng'
        self.assertEqual(self.window.table.item(2, 2).text(), "Đơn đang ship")

        # Hàng cuối cùng (row 3) phải là 'Giao hàng thành công'
        self.assertEqual(self.window.table.item(3, 2).text(), "Đơn giao xong")

        # STT phải luôn là 1, 2, 3, 4
        for r in range(4):
            self.assertEqual(self.window.table.item(r, 0).text(), str(r + 1))


if __name__ == '__main__':
    unittest.main()
