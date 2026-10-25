"""
Module quản lý cơ sở dữ liệu SQLite cho ứng dụng Theo dõi hành trình đơn hàng.
Lưu trữ thông tin đơn hàng cục bộ trên máy tính người dùng.
"""

import sqlite3
import os
import shutil
import json
import re
from datetime import datetime
from pathlib import Path


def get_data_dir():
    """Trả về thư mục lưu dữ liệu ứng dụng, ổn định trên Windows."""
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    data_dir = os.path.join(app_data, 'TheoDoiHanhTrinhDonHang')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_db_path():
    """Trả về đường dẫn file database."""
    return os.path.join(get_data_dir(), 'orders.db')


def format_created_date(created_at_str=None):
    """
    Chuyển đổi chuỗi created_at thành định dạng ngày dd/mm/yyyy.
    Ví dụ: '2026-10-18 11:17:18' -> '18/10/2026'.
    Nếu không có created_at_str, trả về ngày hiện tại.
    """
    if not created_at_str:
        return datetime.now().strftime('%d/%m/%Y')
    try:
        clean_str = str(created_at_str).strip()
        date_part = clean_str.split(' ')[0].split('T')[0]
        parts = date_part.split('-')
        if len(parts) == 3:
            return f"{int(parts[2]):02d}/{int(parts[1]):02d}/{parts[0]}"
    except Exception:
        pass
    return datetime.now().strftime('%d/%m/%Y')


def append_created_date_to_product(product_name, created_at_str=None):
    """
    Tự động ghi chú thêm ngày tạo đơn vào sau tên sản phẩm nếu chưa có.
    Ví dụ: 'Áo thun' -> 'Áo thun (18/10/2026)'.
    Nếu đã có ngày tạo ở đuôi (dạng (dd/mm/yyyy) hoặc (dd/mm)) thì giữ nguyên,
    không bao giờ thay đổi hay thêm trùng lặp.
    """
    name = (product_name or '').strip()
    if not name:
        return name
    # Kiểm tra xem tên sản phẩm đã có phần ngày trong ngoặc ở cuối chưa
    if re.search(r'\(\s*(?:ng[àa]y\s+)?\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\s*\)\s*$', name, re.IGNORECASE):
        return name
    date_str = format_created_date(created_at_str)
    return f"{name} ({date_str})"


class DatabaseManager:
    """Quản lý cơ sở dữ liệu SQLite."""

    def __init__(self, db_path=None):
        self.db_path = db_path or get_db_path()
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Kết nối đến database."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể kết nối cơ sở dữ liệu: {e}")

    def _create_tables(self):
        """Tạo bảng nếu chưa tồn tại và tự động cập nhật schema (migration)."""
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT DEFAULT '',
                    product_name TEXT DEFAULT '',
                    tracking_code TEXT DEFAULT '',
                    carrier TEXT DEFAULT '',
                    journey_status TEXT DEFAULT '',
                    journey_detail TEXT DEFAULT '',
                    amount REAL DEFAULT 0,
                    amount_text TEXT DEFAULT '',
                    phone_last4 TEXT DEFAULT '',
                    address TEXT DEFAULT '',
                    extra_data TEXT DEFAULT '{}',
                    last_query_time TEXT DEFAULT '',
                    last_error TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)
            self.conn.commit()

            # Migration: thêm cột address nếu DB cũ chưa có
            try:
                self.conn.execute("ALTER TABLE orders ADD COLUMN address TEXT DEFAULT ''")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

            # Migration: thêm cột extra_data nếu DB cũ chưa có
            try:
                self.conn.execute("ALTER TABLE orders ADD COLUMN extra_data TEXT DEFAULT '{}'")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

            # Bảng quản lý các cột tùy biến do người dùng thêm vào
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_columns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể tạo bảng dữ liệu: {e}")

    def add_order(self, account_name='', product_name='', tracking_code='',
                  carrier='', amount=0, amount_text='', phone_last4='',
                  address='', extra_data='{}'):
        """Thêm đơn hàng mới. Trả về ID của đơn hàng."""
        if isinstance(extra_data, dict):
            extra_data = json.dumps(extra_data, ensure_ascii=False)
        try:
            cursor = self.conn.execute("""
                INSERT INTO orders (account_name, product_name, tracking_code,
                                   carrier, amount, amount_text, phone_last4,
                                   address, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (account_name, product_name, tracking_code,
                  carrier, amount, amount_text, phone_last4,
                  address, extra_data))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể thêm đơn hàng: {e}")

    def update_order(self, order_id, **kwargs):
        """Cập nhật thông tin đơn hàng theo ID."""
        allowed_fields = {
            'account_name', 'product_name', 'tracking_code', 'carrier',
            'journey_status', 'journey_detail', 'amount', 'amount_text',
            'phone_last4', 'last_query_time', 'last_error', 'address', 'extra_data'
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return

        if 'extra_data' in fields and isinstance(fields['extra_data'], dict):
            fields['extra_data'] = json.dumps(fields['extra_data'], ensure_ascii=False)

        fields['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        values = list(fields.values()) + [order_id]

        try:
            self.conn.execute(
                f"UPDATE orders SET {set_clause} WHERE id = ?", values
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể cập nhật đơn hàng: {e}")

    def update_journey(self, order_id, status, detail=''):
        """Cập nhật hành trình đơn hàng sau khi tra cứu thành công.
        Chỉ cập nhật cột journey, không ảnh hưởng các cột khác."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.conn.execute("""
                UPDATE orders SET journey_status = ?, journey_detail = ?,
                    last_query_time = ?, last_error = '',
                    updated_at = ?
                WHERE id = ?
            """, (status, detail, now, now, order_id))
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể cập nhật hành trình: {e}")

    def update_query_error(self, order_id, error_msg):
        """Ghi nhận lỗi tra cứu. KHÔNG ghi đè trạng thái thành công cũ."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.conn.execute("""
                UPDATE orders SET last_error = ?, last_query_time = ?,
                    updated_at = ?
                WHERE id = ?
            """, (error_msg, now, now, order_id))
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể ghi nhận lỗi tra cứu: {e}")

    def delete_order(self, order_id):
        """Xóa đơn hàng theo ID."""
        try:
            self.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể xóa đơn hàng: {e}")

    def delete_orders(self, order_ids):
        """Xóa nhiều đơn hàng."""
        if not order_ids:
            return
        placeholders = ','.join('?' * len(order_ids))
        try:
            self.conn.execute(
                f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể xóa đơn hàng: {e}")

    def get_all_orders(self):
        """Lấy tất cả đơn hàng."""
        try:
            cursor = self.conn.execute(
                "SELECT * FROM orders ORDER BY id ASC"
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể đọc dữ liệu: {e}")

    def get_order(self, order_id):
        """Lấy thông tin một đơn hàng."""
        try:
            cursor = self.conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể đọc dữ liệu: {e}")

    def search_orders(self, keyword):
        """Tìm kiếm đơn hàng theo từ khóa."""
        keyword = f'%{keyword}%'
        try:
            cursor = self.conn.execute("""
                SELECT * FROM orders
                WHERE account_name LIKE ? OR product_name LIKE ?
                    OR tracking_code LIKE ?
                ORDER BY id ASC
            """, (keyword, keyword, keyword))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể tìm kiếm: {e}")

    def check_tracking_code_exists(self, tracking_code, exclude_id=None):
        """Kiểm tra mã vận đơn đã tồn tại chưa."""
        if not tracking_code:
            return False
        try:
            if exclude_id:
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE tracking_code = ? AND id != ?",
                    (tracking_code, exclude_id)
                )
            else:
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE tracking_code = ?",
                    (tracking_code,)
                )
            return cursor.fetchone()[0] > 0
        except sqlite3.Error:
            return False

    def backup_database(self, backup_path=None):
        """Sao lưu cơ sở dữ liệu."""
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(get_data_dir(), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f'orders_backup_{timestamp}.db')

        try:
            # Đóng WAL trước khi sao lưu
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        except Exception as e:
            raise RuntimeError(f"Không thể sao lưu: {e}")

    def restore_database(self, backup_path):
        """Khôi phục cơ sở dữ liệu từ bản sao lưu."""
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Không tìm thấy file sao lưu: {backup_path}")

        try:
            self.conn.close()
            shutil.copy2(backup_path, self.db_path)
            self._connect()
            return True
        except Exception as e:
            self._connect()  # Reconnect to original
            raise RuntimeError(f"Không thể khôi phục: {e}")

    def get_backup_list(self):
        """Lấy danh sách các bản sao lưu."""
        backup_dir = os.path.join(get_data_dir(), 'backups')
        if not os.path.exists(backup_dir):
            return []
        files = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.db'):
                path = os.path.join(backup_dir, f)
                size = os.path.getsize(path)
                files.append({'name': f, 'path': path, 'size': size})
        return files

    def get_custom_columns(self):
        """Lấy danh sách các cột tùy chọn do người dùng tạo."""
        try:
            cursor = self.conn.execute("SELECT name FROM custom_columns ORDER BY id ASC")
            return [row['name'] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def add_custom_column(self, name):
        """Thêm một cột tùy chọn mới."""
        name = str(name).strip()
        if not name:
            raise ValueError("Tên cột không được để trống")
        try:
            self.conn.execute("INSERT INTO custom_columns (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            raise ValueError(f"Cột '{name}' đã tồn tại")
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể thêm cột tùy chọn: {e}")

    def delete_custom_column(self, name):
        """Xóa một cột tùy chọn."""
        try:
            self.conn.execute("DELETE FROM custom_columns WHERE name = ?", (name,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            raise RuntimeError(f"Không thể xóa cột tùy chọn: {e}")

    def update_order_extra(self, order_id, col_name, value):
        """Cập nhật giá trị của một cột tùy chọn cho đơn hàng."""
        order = self.get_order(order_id)
        if not order:
            return
        extra_str = order.get('extra_data') or '{}'
        try:
            extra_dict = json.loads(extra_str)
        except Exception:
            extra_dict = {}
        extra_dict[col_name] = str(value)
        self.update_order(order_id, extra_data=extra_dict)

    def migrate_product_creation_dates(self):
        """Tự động cập nhật thêm ngày tạo đơn vào sau tên sản phẩm cho các đơn hàng cũ chưa có."""
        try:
            cursor = self.conn.execute(
                "SELECT id, product_name, created_at FROM orders WHERE product_name IS NOT NULL AND product_name != ''"
            )
            rows = cursor.fetchall()
            for r in rows:
                oid = r['id']
                pname = r['product_name']
                cat = r['created_at']
                updated_name = append_created_date_to_product(pname, cat)
                if updated_name != pname:
                    self.conn.execute(
                        "UPDATE orders SET product_name = ? WHERE id = ?",
                        (updated_name, oid)
                    )
            self.conn.commit()
        except sqlite3.Error:
            pass

    def close(self):
        """Đóng kết nối database."""
        if self.conn:
            self.conn.close()
            self.conn = None
