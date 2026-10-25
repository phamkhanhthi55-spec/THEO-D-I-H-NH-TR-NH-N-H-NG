"""
Kiểm thử module database.
"""

import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    DatabaseManager, format_created_date, append_created_date_to_product
)
from src.carrier import detect_carrier, validate_tracking_code, CARRIER_SPX, CARRIER_GHN, CARRIER_UNKNOWN
from src.data_io import parse_amount, format_amount


class TestDatabase(unittest.TestCase):
    """Test DatabaseManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.db.close()

    def test_add_order(self):
        """Test thêm đơn hàng."""
        order_id = self.db.add_order(
            account_name='test_acc',
            product_name='Sản phẩm test',
            tracking_code='SPXVN012345678',
            carrier='SPX',
            amount=250000,
            amount_text='250.000 ₫'
        )
        self.assertIsNotNone(order_id)
        self.assertGreater(order_id, 0)

    def test_get_order(self):
        """Test đọc đơn hàng."""
        oid = self.db.add_order(
            account_name='acc1',
            product_name='SP1',
            tracking_code='SPXVN111111111'
        )
        order = self.db.get_order(oid)
        self.assertEqual(order['account_name'], 'acc1')
        self.assertEqual(order['product_name'], 'SP1')
        self.assertEqual(order['tracking_code'], 'SPXVN111111111')

    def test_update_order(self):
        """Test cập nhật đơn hàng."""
        oid = self.db.add_order(account_name='old_name')
        self.db.update_order(oid, account_name='new_name', product_name='SP mới')
        order = self.db.get_order(oid)
        self.assertEqual(order['account_name'], 'new_name')
        self.assertEqual(order['product_name'], 'SP mới')

    def test_update_journey_not_affect_other_fields(self):
        """Test cập nhật hành trình không ảnh hưởng cột khác."""
        oid = self.db.add_order(
            account_name='acc_test',
            product_name='SP_test',
            amount=500000,
            amount_text='500.000 ₫'
        )
        self.db.update_journey(oid, 'Đã giao', 'Chi tiết hành trình')
        order = self.db.get_order(oid)
        # Các trường khác phải giữ nguyên
        self.assertEqual(order['account_name'], 'acc_test')
        self.assertEqual(order['product_name'], 'SP_test')
        self.assertEqual(order['amount'], 500000)
        self.assertEqual(order['amount_text'], '500.000 ₫')
        # Journey phải được cập nhật
        self.assertEqual(order['journey_status'], 'Đã giao')

    def test_update_error_not_overwrite_status(self):
        """Test ghi lỗi không ghi đè trạng thái thành công."""
        oid = self.db.add_order(tracking_code='TEST123')
        self.db.update_journey(oid, 'Đang giao hàng', 'detail')
        self.db.update_query_error(oid, 'Lỗi mạng')

        order = self.db.get_order(oid)
        # Trạng thái thành công phải vẫn còn
        self.assertEqual(order['journey_status'], 'Đang giao hàng')
        # Lỗi phải được ghi
        self.assertEqual(order['last_error'], 'Lỗi mạng')

    def test_delete_order(self):
        """Test xóa đơn hàng."""
        oid = self.db.add_order(account_name='to_delete')
        self.db.delete_order(oid)
        order = self.db.get_order(oid)
        self.assertIsNone(order)

    def test_delete_multiple(self):
        """Test xóa nhiều đơn hàng."""
        ids = [self.db.add_order(account_name=f'acc{i}') for i in range(5)]
        self.db.delete_orders(ids[:3])
        orders = self.db.get_all_orders()
        self.assertEqual(len(orders), 2)

    def test_search(self):
        """Test tìm kiếm."""
        self.db.add_order(account_name='Nguyễn Văn A', product_name='Áo')
        self.db.add_order(account_name='Trần Thị B', product_name='Quần')
        results = self.db.search_orders('Nguyễn')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['account_name'], 'Nguyễn Văn A')

    def test_vietnamese_text(self):
        """Test lưu trữ tiếng Việt."""
        oid = self.db.add_order(
            account_name='Phạm Khánh Thi',
            product_name='Áo khoác mùa đông'
        )
        order = self.db.get_order(oid)
        self.assertEqual(order['account_name'], 'Phạm Khánh Thi')
        self.assertEqual(order['product_name'], 'Áo khoác mùa đông')

    def test_data_persistence(self):
        """Test dữ liệu tồn tại sau khi đóng mở lại."""
        self.db.add_order(account_name='persistent_acc')
        self.db.close()

        db2 = DatabaseManager(self.db_path)
        orders = db2.get_all_orders()
        db2.close()

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['account_name'], 'persistent_acc')

    def test_check_duplicate_tracking(self):
        """Test kiểm tra mã vận đơn trùng."""
        self.db.add_order(tracking_code='SPXVN123456789')
        self.assertTrue(self.db.check_tracking_code_exists('SPXVN123456789'))
        self.assertFalse(self.db.check_tracking_code_exists('SPXVN999999999'))

    def test_backup_restore(self):
        """Test sao lưu và khôi phục."""
        self.db.add_order(account_name='backup_test')
        backup_path = self.db.backup_database(
            os.path.join(self.temp_dir, 'backup.db'))
        self.assertTrue(os.path.exists(backup_path))

        # Xóa dữ liệu
        orders = self.db.get_all_orders()
        self.db.delete_orders([o['id'] for o in orders])
        self.assertEqual(len(self.db.get_all_orders()), 0)

        # Khôi phục
        self.db.restore_database(backup_path)
        orders = self.db.get_all_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['account_name'], 'backup_test')

    def test_amount_not_changed_on_journey_update(self):
        """Test số tiền KHÔNG bị thay đổi khi cập nhật hành trình."""
        oid = self.db.add_order(
            amount=1500000,
            amount_text='1.500.000 ₫'
        )
        self.db.update_journey(oid, 'Đã giao thành công', 'detail')

        order = self.db.get_order(oid)
        self.assertEqual(order['amount'], 1500000)
        self.assertEqual(order['amount_text'], '1.500.000 ₫')


class TestCarrier(unittest.TestCase):
    """Test carrier detection."""

    def test_spx_detection(self):
        """Test nhận diện SPX."""
        self.assertEqual(detect_carrier('SPXVN012345678901'), CARRIER_SPX)
        self.assertEqual(detect_carrier('SPX012345678'), CARRIER_SPX)
        self.assertEqual(detect_carrier('spxvn012345678901'), CARRIER_SPX)

    def test_unknown_detection(self):
        """Test mã không xác định."""
        self.assertEqual(detect_carrier('RANDOM123'), CARRIER_UNKNOWN)
        self.assertEqual(detect_carrier(''), CARRIER_UNKNOWN)
        self.assertEqual(detect_carrier(None), CARRIER_UNKNOWN)

    def test_validation(self):
        """Test validate mã vận đơn."""
        self.assertTrue(validate_tracking_code('SPXVN012345678')[0])
        self.assertFalse(validate_tracking_code('')[0])
        self.assertFalse(validate_tracking_code('AB')[0])
        self.assertFalse(validate_tracking_code('ABC!@#')[0])


class TestAmount(unittest.TestCase):
    """Test xử lý số tiền."""

    def test_parse_amount(self):
        """Test phân tích số tiền."""
        self.assertEqual(parse_amount('250000'), 250000)
        self.assertEqual(parse_amount('250.000'), 250000)
        self.assertEqual(parse_amount('250,000'), 250000)
        self.assertEqual(parse_amount('1.500.000'), 1500000)
        self.assertEqual(parse_amount('250.000 ₫'), 250000)
        self.assertEqual(parse_amount(250000), 250000)
        self.assertEqual(parse_amount(''), 0)
        self.assertEqual(parse_amount(None), 0)

    def test_format_amount(self):
        """Test định dạng số tiền."""
        self.assertEqual(format_amount(250000), '250.000 ₫')
        self.assertEqual(format_amount(1500000), '1.500.000 ₫')
        self.assertEqual(format_amount(0), '')
        self.assertEqual(format_amount(None), '')

    def test_amount_roundtrip(self):
        """Test chuyển đổi qua lại không mất dữ liệu."""
        original = 1500000
        formatted = format_amount(original)
        parsed = parse_amount(formatted)
        self.assertEqual(parsed, original)


class TestColumnOrder(unittest.TestCase):
    """Test thứ tự cột."""

    def test_column_order(self):
        """Test đúng thứ tự 7 cột cơ bản."""
        expected = ['STT', 'Tên acc đặt', 'Tên SP', 'Mã vận đơn',
                    'Hành trình di chuyển', 'Số tiền cần thanh toán', 'Địa chỉ']
        from src.main_window import MainWindow
        self.assertEqual(MainWindow.COLUMNS, expected)
        self.assertEqual(MainWindow.COL_COUNT, 7)


class TestProductCreationDate(unittest.TestCase):
    """Test tự động thêm và giữ nguyên ngày tạo đơn vào sau tên sản phẩm."""

    def test_format_created_date(self):
        """Test chuyển đổi chuỗi created_at thành dd/mm/yyyy."""
        self.assertEqual(format_created_date('2026-10-18 11:17:18'), '18/10/2026')
        self.assertEqual(format_created_date('2026-10-23 17:13:36'), '23/10/2026')
        self.assertEqual(format_created_date('2026-05-09'), '09/05/2026')

    def test_append_created_date(self):
        """Test thêm ngày tạo đơn vào sau tên sản phẩm nếu chưa có."""
        res = append_created_date_to_product('ÁO CHO TUN', '2026-10-18 11:17:18')
        self.assertEqual(res, 'ÁO CHO TUN (18/10/2026)')

        # Nếu đã có ngày tạo ở đuôi thì giữ nguyên, không nhân đôi
        res2 = append_created_date_to_product('ÁO CHO TUN (18/10/2026)', '2026-10-18 11:17:18')
        self.assertEqual(res2, 'ÁO CHO TUN (18/10/2026)')

        res3 = append_created_date_to_product('ÁO CHO TUN (18/10)', '2026-10-18 11:17:18')
        self.assertEqual(res3, 'ÁO CHO TUN (18/10)')

        # Rỗng
        self.assertEqual(append_created_date_to_product(''), '')
        self.assertEqual(append_created_date_to_product(None), '')

    def test_migrate_existing_orders(self):
        """Test migration tự động gắn ngày tạo cho các đơn hàng cũ."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'migrate_test.db')
        db = DatabaseManager(db_path)

        # Thêm thủ công đơn hàng chưa có ngày
        db.conn.execute(
            "INSERT INTO orders (account_name, product_name, created_at) VALUES (?, ?, ?)",
            ('acc1', 'Áo khoác', '2026-10-18 10:00:00')
        )
        db.conn.execute(
            "INSERT INTO orders (account_name, product_name, created_at) VALUES (?, ?, ?)",
            ('acc2', 'Quần jean (19/10/2026)', '2026-10-19 12:00:00')
        )
        db.conn.commit()

        # Chạy migration
        db.migrate_product_creation_dates()

        orders = db.get_all_orders()
        db.close()

        self.assertEqual(orders[0]['product_name'], 'Áo khoác (18/10/2026)')
        self.assertEqual(orders[1]['product_name'], 'Quần jean (19/10/2026)')

    def test_preserve_creation_date_on_edit(self):
        """Test khi sửa tên sản phẩm thì ngày tạo gốc vẫn được giữ nguyên không đổi."""
        original_created_at = '2026-10-18 11:17:18'
        # Người dùng sửa tên sản phẩm thành tên mới không chứa ngày
        edited_name = 'Áo thun polo mới'
        preserved_name = append_created_date_to_product(edited_name, original_created_at)
        self.assertEqual(preserved_name, 'Áo thun polo mới (18/10/2026)')


if __name__ == '__main__':
    unittest.main()
