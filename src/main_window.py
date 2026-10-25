"""
Giao diện chính của ứng dụng Theo dõi hành trình đơn hàng.
Sử dụng PySide6 (Qt6) với bảng dữ liệu kiểu bảng tính.
"""

import sys
import os
import webbrowser
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QHeaderView, QMessageBox, QFileDialog, QComboBox, QDialog,
    QFormLayout, QDialogButtonBox, QTextEdit, QProgressBar,
    QAbstractItemView, QStatusBar, QMenu, QToolBar, QGroupBox,
    QSplitter, QFrame, QSizePolicy, QCheckBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QSize, QTimer
)
from PySide6.QtGui import (
    QIcon, QFont, QColor, QAction, QKeySequence, QPalette, QPixmap,
    QPainter, QLinearGradient
)

from .database import DatabaseManager, get_data_dir, append_created_date_to_product
from .carrier import (
    detect_carrier, get_carrier_name, validate_tracking_code,
    CARRIER_SPX, CARRIER_GHN, CARRIER_UNKNOWN, needs_phone_last4
)
from .data_io import (
    import_file, export_excel, export_csv, format_amount, parse_amount
)


def get_resource_path(relative_path):
    """Lấy đường dẫn tài nguyên chuẩn xác cho cả khi chạy mã nguồn và khi đóng gói .exe."""
    # 1. PyInstaller MEIPASS
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(p):
            return p

    # 2. Thư mục chạy thực tế của file .exe (onedir)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        for sub in ['', '_internal']:
            p = os.path.join(exe_dir, sub, relative_path) if sub else os.path.join(exe_dir, relative_path)
            if os.path.exists(p):
                return p

    # 3. Khi chạy code trực tiếp (development)
    cur_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(cur_file)
    project_root = os.path.dirname(src_dir)
    for base in [project_root, src_dir, os.path.abspath('.')]:
        p = os.path.join(base, relative_path)
        if os.path.exists(p):
            return p

    return os.path.join(project_root, relative_path)


# ============================================================
# Worker thread cho tra cứu vận đơn (không block UI)
# ============================================================

class TrackingWorker(QThread):
    """Thread tra cứu vận đơn không block giao diện."""
    progress = Signal(int, int, str)   # current, total, message
    result = Signal(int, bool, str, str, str)  # order_id, success, status, detail, error
    finished_all = Signal(int, int)     # success_count, fail_count

    def __init__(self, orders_to_track):
        super().__init__()
        self.orders_to_track = orders_to_track  # [(order_id, tracking_code, carrier, phone_last4)]
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from .tracking import track_order

        total = len(self.orders_to_track)
        success_count = 0
        fail_count = 0

        for idx, item in enumerate(self.orders_to_track):
            if self._cancelled:
                break

            order_id = item[0]
            tracking_code = item[1]
            carrier = item[2]
            phone_last4 = item[3] if len(item) > 3 else ''
            existing_status = item[4] if len(item) > 4 else ''
            existing_detail = item[5] if len(item) > 5 else ''

            self.progress.emit(idx + 1, total,
                               f"Đang tra cứu {tracking_code} ({idx+1}/{total})...")

            try:
                result = track_order(tracking_code, carrier, phone_last4)
                if result.success:
                    success_count += 1
                    self.result.emit(order_id, True, result.status,
                                    result.detail, '')
                elif existing_status:
                    # Đơn hàng đã có hành trình trước đó, nếu lần này chưa có cập nhật mới từ hãng
                    # hoặc trạng thái dậm chân tại chỗ: vẫn bảo lưu trạng thái thành công và cập nhật giờ tra cứu
                    success_count += 1
                    self.result.emit(order_id, True, existing_status,
                                    existing_detail, '')
                else:
                    fail_count += 1
                    self.result.emit(order_id, False, '', '',
                                    result.error)
            except Exception as e:
                if existing_status:
                    success_count += 1
                    self.result.emit(order_id, True, existing_status,
                                    existing_detail, '')
                else:
                    fail_count += 1
                    self.result.emit(order_id, False, '', '',
                                    f"Lỗi: {str(e)[:200]}")

        self.finished_all.emit(success_count, fail_count)


# ============================================================
# Dialog thêm/sửa đơn hàng
# ============================================================

class OrderDialog(QDialog):
    """Dialog thêm hoặc sửa đơn hàng."""

    def __init__(self, parent=None, order=None, db=None):
        super().__init__(parent)
        self.order = order
        self.db = db
        self.setWindowTitle("🌸 Sửa đơn hàng" if order else "✨ Thêm đơn hàng mới")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFF5F8;
                color: #4A3B43;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                font-weight: 600;
                color: #AD1457;
            }
            QLineEdit, QComboBox {
                background-color: #FFFFFF;
                border: 1.5px solid #FFB6C1;
                border-radius: 10px;
                padding: 6px 12px;
                color: #4A3B43;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #FF6F89;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #C2185B;
                border: 1.5px solid #FFB6C1;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFEAF0;
            }
        """)
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == 'win32':
            try:
                set_window_titlebar_pastel_yellow(int(self.winId()))
            except Exception:
                pass

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)

        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("Nhập tên tài khoản đặt hàng")
        layout.addRow("Tên acc đặt:", self.account_edit)

        self.product_edit = QLineEdit()
        self.product_edit.setPlaceholderText("Nhập tên sản phẩm")
        layout.addRow("Tên SP:", self.product_edit)

        self.tracking_edit = QLineEdit()
        self.tracking_edit.setPlaceholderText("Nhập mã vận đơn (VD: SPXVN012345678)")
        layout.addRow("Mã vận đơn:", self.tracking_edit)

        # Đơn vị vận chuyển
        carrier_layout = QHBoxLayout()
        self.carrier_combo = QComboBox()
        self.carrier_combo.addItem("Tự động nhận diện", "")
        self.carrier_combo.addItem("Shopee Express (SPX)", CARRIER_SPX)
        self.carrier_combo.addItem("Giao Hàng Nhanh (GHN)", CARRIER_GHN)
        carrier_layout.addWidget(self.carrier_combo)

        self.carrier_label = QLabel("")
        self.carrier_label.setStyleSheet("color: #666; font-style: italic;")
        carrier_layout.addWidget(self.carrier_label)
        layout.addRow("Đơn vị vận chuyển:", carrier_layout)

        # 4 số cuối SĐT (cho GHN)
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("4 số cuối SĐT đặt hàng (chỉ cho GHN)")
        self.phone_edit.setMaxLength(4)
        self.phone_label = QLabel("4 số cuối SĐT:")
        layout.addRow(self.phone_label, self.phone_edit)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("VD: 250000 hoặc 250.000")
        layout.addRow("Số tiền cần thanh toán:", self.amount_edit)

        # Địa chỉ (tùy chọn Bình Định / Quy Nhơn)
        self.address_combo = QComboBox()
        self.address_combo.setEditable(True)
        self.address_combo.addItem("")
        self.address_combo.addItem("Bình Định")
        self.address_combo.addItem("Quy Nhơn")
        layout.addRow("Địa chỉ:", self.address_combo)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept_order)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

        # Connect signals
        self.tracking_edit.textChanged.connect(self.on_tracking_changed)
        self.carrier_combo.currentIndexChanged.connect(self.on_carrier_changed)

        # Điền dữ liệu nếu sửa
        if self.order:
            self.account_edit.setText(self.order.get('account_name', ''))
            self.product_edit.setText(self.order.get('product_name', ''))
            self.tracking_edit.setText(self.order.get('tracking_code', ''))

            carrier = self.order.get('carrier', '')
            idx = self.carrier_combo.findData(carrier)
            if idx >= 0:
                self.carrier_combo.setCurrentIndex(idx)

            self.phone_edit.setText(self.order.get('phone_last4', ''))

            amount_text = self.order.get('amount_text', '')
            if amount_text:
                self.amount_edit.setText(amount_text)
            elif self.order.get('amount', 0):
                self.amount_edit.setText(format_amount(self.order['amount']))

            addr = self.order.get('address', '')
            idx_addr = self.address_combo.findText(addr)
            if idx_addr >= 0:
                self.address_combo.setCurrentIndex(idx_addr)
            elif addr:
                self.address_combo.addItem(addr)
                self.address_combo.setCurrentText(addr)

        self.on_carrier_changed()

    def on_tracking_changed(self, text):
        """Tự động nhận diện đơn vị vận chuyển khi nhập mã."""
        if self.carrier_combo.currentIndex() == 0:  # Tự động
            carrier = detect_carrier(text)
            if carrier != CARRIER_UNKNOWN:
                self.carrier_label.setText(
                    f"→ Nhận diện: {get_carrier_name(carrier)}")
            else:
                self.carrier_label.setText("")

    def on_carrier_changed(self):
        """Hiện/ẩn trường SĐT theo đơn vị vận chuyển."""
        carrier = self.carrier_combo.currentData()
        show_phone = carrier == CARRIER_GHN
        self.phone_edit.setVisible(show_phone)
        self.phone_label.setVisible(show_phone)

    def get_data(self):
        """Trả về dữ liệu đơn hàng từ dialog."""
        tracking_code = self.tracking_edit.text().strip()
        carrier = self.carrier_combo.currentData()

        # Tự động nhận diện nếu chưa chọn
        if not carrier:
            carrier = detect_carrier(tracking_code)

        amount_text = self.amount_edit.text().strip()
        amount = parse_amount(amount_text)

        return {
            'account_name': self.account_edit.text().strip(),
            'product_name': self.product_edit.text().strip(),
            'tracking_code': tracking_code,
            'carrier': carrier,
            'phone_last4': self.phone_edit.text().strip() if carrier == CARRIER_GHN else '',
            'amount': amount,
            'amount_text': amount_text,
            'address': self.address_combo.currentText().strip(),
        }

    def accept_order(self):
        """Xác nhận và kiểm tra dữ liệu."""
        data = self.get_data()

        # Kiểm tra mã vận đơn nếu có nhập
        if data['tracking_code']:
            valid, msg = validate_tracking_code(data['tracking_code'])
            if not valid:
                QMessageBox.warning(self, "Cảnh báo", msg)
                return

            # Kiểm tra trùng mã vận đơn
            if self.db:
                exclude_id = self.order.get('id') if self.order else None
                if self.db.check_tracking_code_exists(
                        data['tracking_code'], exclude_id):
                    reply = QMessageBox.question(
                        self, "Trùng mã vận đơn",
                        f"Mã vận đơn {data['tracking_code']} đã tồn tại.\n"
                        "Bạn vẫn muốn tiếp tục?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return

        # Kiểm tra 4 số cuối SĐT cho GHN
        if data['carrier'] == CARRIER_GHN and data['phone_last4']:
            if len(data['phone_last4']) != 4 or not data['phone_last4'].isdigit():
                QMessageBox.warning(
                    self, "Cảnh báo",
                    "4 số cuối SĐT phải gồm đúng 4 chữ số."
                )
                return

        self.accept()


# ============================================================
# Dialog chi tiết đơn hàng
# ============================================================

class OrderDetailDialog(QDialog):
    """Dialog hiển thị chi tiết đơn hàng."""

    def __init__(self, parent=None, order=None):
        super().__init__(parent)
        self.order = order or {}
        self.setWindowTitle(f"🎀 Chi tiết đơn hàng - {self.order.get('tracking_code', '')}")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFF5F8;
                color: #4A3B43;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1.5px solid #FFCCD5;
                border-radius: 12px;
                margin-top: 10px;
                font-weight: bold;
                color: #D81B60;
                padding-top: 15px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLabel {
                color: #4A3B43;
            }
            QTextEdit {
                background-color: #FFF8FA;
                border: 1px solid #FFCCD5;
                border-radius: 8px;
                padding: 8px;
                color: #4A3B43;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #C2185B;
                border: 1.5px solid #FFB6C1;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFEAF0;
            }
        """)
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == 'win32':
            try:
                set_window_titlebar_pastel_yellow(int(self.winId()))
            except Exception:
                pass

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Thông tin cơ bản
        info_group = QGroupBox("Thông tin đơn hàng")
        info_layout = QFormLayout()
        info_layout.addRow("Tên acc đặt:",
                           QLabel(self.order.get('account_name', '')))
        info_layout.addRow("Tên SP:",
                           QLabel(self.order.get('product_name', '')))
        info_layout.addRow("Mã vận đơn:",
                           QLabel(self.order.get('tracking_code', '')))
        info_layout.addRow("Đơn vị vận chuyển:",
                           QLabel(get_carrier_name(
                               self.order.get('carrier', ''))))

        amount_text = self.order.get('amount_text', '')
        if not amount_text and self.order.get('amount', 0):
            amount_text = format_amount(self.order['amount'])
        info_layout.addRow("Số tiền cần thanh toán:", QLabel(amount_text))

        info_layout.addRow("Địa chỉ:",
                           QLabel(self.order.get('address') or 'Chưa chọn'))

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Hành trình
        journey_group = QGroupBox("Hành trình di chuyển")
        journey_layout = QVBoxLayout()

        status = self.order.get('journey_status', '')
        if status:
            status_label = QLabel(f"Trạng thái: {status}")
            status_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            journey_layout.addWidget(status_label)

        detail = self.order.get('journey_detail', '')
        if detail:
            detail_text = QTextEdit()
            detail_text.setPlainText(detail)
            detail_text.setReadOnly(True)
            journey_layout.addWidget(detail_text)

        last_query = self.order.get('last_query_time', '')
        if last_query:
            journey_layout.addWidget(
                QLabel(f"Tra cứu lần cuối: {last_query}"))

        last_error = self.order.get('last_error', '')
        if last_error:
            error_label = QLabel(f"Lỗi gần nhất: {last_error}")
            error_label.setStyleSheet("color: red;")
            error_label.setWordWrap(True)
            journey_layout.addWidget(error_label)

        if not status and not detail:
            journey_layout.addWidget(QLabel("Chưa tra cứu"))

        journey_group.setLayout(journey_layout)
        layout.addWidget(journey_group)

        # Nút mở trang tra cứu
        btn_layout = QHBoxLayout()
        carrier = self.order.get('carrier', '')
        tracking = self.order.get('tracking_code', '')
        if tracking and carrier in (CARRIER_SPX, CARRIER_GHN):
            open_btn = QPushButton("🌐 Mở trang tra cứu trong trình duyệt")
            open_btn.clicked.connect(
                lambda: self._open_tracking_page(tracking, carrier))
            btn_layout.addWidget(open_btn)

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open_tracking_page(self, tracking_code, carrier):
        from .tracking import open_tracking_url
        open_tracking_url(tracking_code, carrier)


# ============================================================
# Dialog nhập dữ liệu
# ============================================================

class ImportDialog(QDialog):
    """Dialog xác nhận trước khi nhập dữ liệu."""

    def __init__(self, parent=None, order_count=0, duplicate_codes=None):
        super().__init__(parent)
        self.setWindowTitle("📂 Nhập dữ liệu đơn hàng")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFF5F8;
                color: #4A3B43;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                font-weight: 600;
                color: #AD1457;
            }
            QCheckBox {
                color: #4A3B43;
                font-size: 12px;
                padding: 4px;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #C2185B;
                border: 1.5px solid #FFB6C1;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFEAF0;
            }
        """)
        self.mode = 'append'  # append hoặc replace
        self.setup_ui(order_count, duplicate_codes or [])

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == 'win32':
            try:
                set_window_titlebar_pastel_yellow(int(self.winId()))
            except Exception:
                pass

    def setup_ui(self, order_count, duplicate_codes):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"Tìm thấy {order_count} đơn hàng trong file."
        ))

        if duplicate_codes:
            dup_label = QLabel(
                f"⚠️ {len(duplicate_codes)} mã vận đơn đã tồn tại: "
                f"{', '.join(duplicate_codes[:5])}"
                f"{'...' if len(duplicate_codes) > 5 else ''}"
            )
            dup_label.setWordWrap(True)
            dup_label.setStyleSheet("color: #e67e22;")
            layout.addWidget(dup_label)

        layout.addWidget(QLabel("Chọn cách nhập:"))

        self.append_radio = QCheckBox("Thêm vào danh sách hiện tại (giữ dữ liệu cũ)")
        self.append_radio.setChecked(True)
        layout.addWidget(self.append_radio)

        self.replace_radio = QCheckBox("Thay thế toàn bộ dữ liệu hiện tại")
        layout.addWidget(self.replace_radio)

        # Mutual exclusion
        self.append_radio.toggled.connect(
            lambda checked: self.replace_radio.setChecked(not checked) if checked else None
        )
        self.replace_radio.toggled.connect(
            lambda checked: self.append_radio.setChecked(not checked) if checked else None
        )

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_mode(self):
        return 'replace' if self.replace_radio.isChecked() else 'append'


# ============================================================
# Cửa sổ chính
# ============================================================

def set_window_titlebar_pastel_yellow(hwnd):
    """Thiết lập màu thanh tiêu đề Windows 11 sang màu vàng pastel (#FFF3CD)."""
    try:
        import ctypes
        from ctypes import wintypes

        # DWMWA_CAPTION_COLOR = 35 (#FFF3CD -> COLORREF: 0x00CDF3FF)
        caption_color = wintypes.DWORD(0x00CDF3FF)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
        )

        # DWMWA_TEXT_COLOR = 36 (#5D4037 -> COLORREF: 0x0037405D)
        text_color = wintypes.DWORD(0x0037405D)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color)
        )
    except Exception:
        pass


class PastelHeaderView(QHeaderView):
    """Header tùy biến: Cột 0 (STT) hiển thị màu vàng pastel, các cột khác màu hồng pastel."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setHighlightSections(True)

    def paintSection(self, painter: QPainter, rect, logicalIndex):
        painter.save()
        if logicalIndex == 0:
            # Cột STT: Vàng Pastel
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, QColor("#FFF9D2"))
            grad.setColorAt(1, QColor("#FEF3C7"))
            painter.fillRect(rect, grad)
            painter.setPen(QColor("#FFE082"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

            painter.setPen(QColor("#795548"))  # Nâu ấm pastel nhẹ nhàng, không dùng màu đen
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            text = self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole)
            painter.drawText(rect, Qt.AlignCenter, str(text) if text else "STT")
        else:
            # Các cột khác: Hồng Pastel
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, QColor("#FF94A8"))
            grad.setColorAt(1, QColor("#FF7891"))
            painter.fillRect(rect, grad)
            painter.setPen(QColor("#FFA6B8"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            text = self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole)
            if logicalIndex == 4:
                # Dành khoảng trống bên phải cho nút "🔃 Sắp xếp"
                text_rect = rect.adjusted(8, 0, -100, 0)
            else:
                text_rect = rect.adjusted(8, 0, -8, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, str(text) if text else "")

        # Vẽ mũi tên sắp xếp nếu cột này đang được sort
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logicalIndex:
            arrow = " ▲" if self.sortIndicatorOrder() == Qt.AscendingOrder else " ▼"
            painter.setPen(QColor("#795548") if logicalIndex == 0 else QColor("#FFFFFF"))
            if logicalIndex == 4:
                arrow_rect = rect.adjusted(0, 0, -102, 0)
            else:
                arrow_rect = rect.adjusted(0, 0, -6, 0)
            painter.drawText(arrow_rect, Qt.AlignVCenter | Qt.AlignRight, arrow)

        painter.restore()


class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng."""

    BASE_COLUMNS = ['STT', 'Tên acc đặt', 'Tên SP', 'Mã vận đơn',
                    'Hành trình di chuyển', 'Số tiền cần thanh toán', 'Địa chỉ']
    COL_STT = 0
    COL_ACCOUNT = 1
    COL_PRODUCT = 2
    COL_TRACKING = 3
    COL_JOURNEY = 4
    COL_AMOUNT = 5
    COL_ADDRESS = 6
    COL_COUNT = 7

    class _ColumnsDescriptor:
        def __get__(self, obj, objtype=None):
            if obj is None:
                return objtype.BASE_COLUMNS
            return obj.BASE_COLUMNS + getattr(obj, 'custom_columns', [])

    COLUMNS = _ColumnsDescriptor()

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.db.migrate_product_creation_dates()
        self.all_orders = []          # Toàn bộ đơn hàng từ DB
        self.filtered_orders = []     # Đơn hàng sau khi lọc
        self.custom_columns = self.db.get_custom_columns()
        self.tracking_worker = None
        self.current_filter_carrier = ''
        self.current_search_text = ''
        self.current_sort_column = -1
        self.current_sort_order = Qt.AscendingOrder
        self._loading_data = False

        self.setWindowTitle("Theo dõi hành trình đơn hàng")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)

        # Tạo icon
        self._set_app_icon()

        self.setup_ui()
        self.load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_header_sort_button_geometry()
        if sys.platform == 'win32':
            try:
                set_window_titlebar_pastel_yellow(int(self.winId()))
            except Exception:
                pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_header_sort_button_geometry()

    def _update_header_sort_button_geometry(self, *args):
        """Định vị nút sắp xếp nằm ngay trên tiêu đề cột Hành trình di chuyển."""
        if not hasattr(self, 'btn_sort_in_header') or not hasattr(self, 'table'):
            return
        header = self.table.horizontalHeader()
        col = self.COL_JOURNEY
        if col >= header.count() or header.isSectionHidden(col):
            self.btn_sort_in_header.hide()
            return

        x = header.sectionViewportPosition(col)
        w = header.sectionSize(col)
        h = header.height()

        btn_w = 88
        btn_h = min(24, max(20, h - 8))
        btn_x = x + w - btn_w - 8
        btn_y = (h - btn_h) // 2

        if btn_x < x + 10 or w < 120:
            self.btn_sort_in_header.hide()
        else:
            self.btn_sort_in_header.setGeometry(btn_x, btn_y, btn_w, btn_h)
            self.btn_sort_in_header.show()
            self.btn_sort_in_header.raise_()

    def _set_app_icon(self):
        """Thiết lập icon ứng dụng Hello Kitty."""
        for name in ['hello_kitty.ico', 'hello_kitty.png', 'icon.ico', 'icon.png']:
            p = get_resource_path(os.path.join('resources', name))
            if os.path.exists(p):
                self.setWindowIcon(QIcon(p))
                break

    def setup_ui(self):
        """Thiết lập giao diện với tone màu hồng pastel - trắng dễ thương & Hello Kitty."""
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 12, 14, 12)

        # ---- Tiêu đề phong cách Hello Kitty Pastel ----
        header_widget = QWidget()
        header_widget.setObjectName("headerWidget")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 8, 15, 8)
        header_layout.setAlignment(Qt.AlignCenter)

        kitty_path = get_resource_path(os.path.join('resources', 'hello_kitty.png'))

        # Hello Kitty sticker bên trái
        if os.path.exists(kitty_path):
            kitty_left = QLabel()
            pix_left = QPixmap(kitty_path).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            kitty_left.setPixmap(pix_left)
            header_layout.addWidget(kitty_left)

        title_container = QVBoxLayout()
        title_container.setSpacing(2)
        title_container.setAlignment(Qt.AlignCenter)

        title_label = QLabel("🎀 Theo dõi hành trình đơn hàng 🎀")
        title_label.setObjectName("titleLabel")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_container.addWidget(title_label)

        subtitle_label = QLabel("✨ SPX Express & Giao Hàng Nhanh ✨")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setFont(QFont("Segoe UI", 10))
        subtitle_label.setAlignment(Qt.AlignCenter)
        title_container.addWidget(subtitle_label)

        header_layout.addLayout(title_container)

        # Hello Kitty sticker bên phải
        if os.path.exists(kitty_path):
            kitty_right = QLabel()
            pix_right = QPixmap(kitty_path).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            kitty_right.setPixmap(pix_right)
            header_layout.addWidget(kitty_right)

        main_layout.addWidget(header_widget)

        # ---- Thanh công cụ trên ----
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        # Nút quản lý
        self.btn_add = QPushButton("✨ ➕ Thêm")
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.setToolTip("Thêm đơn hàng mới bằng cửa sổ")
        self.btn_add.clicked.connect(self.add_order)
        toolbar_layout.addWidget(self.btn_add)

        self.btn_add_row = QPushButton("➕ Thêm dòng")
        self.btn_add_row.setToolTip("Thêm 1 dòng trống mới vào bảng để nhập trực tiếp")
        self.btn_add_row.clicked.connect(self.add_quick_row)
        toolbar_layout.addWidget(self.btn_add_row)

        self.btn_add_column = QPushButton("🌸 ➕ Thêm cột")
        self.btn_add_column.setToolTip("Thêm một cột tùy chọn mới vào bảng")
        self.btn_add_column.clicked.connect(self.add_custom_column_dialog)
        toolbar_layout.addWidget(self.btn_add_column)

        self.btn_edit = QPushButton("✏️ Sửa")
        self.btn_edit.setToolTip("Sửa đơn hàng đã chọn bằng cửa sổ")
        self.btn_edit.clicked.connect(self.edit_order)
        toolbar_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑️ Xóa")
        self.btn_delete.setObjectName("deleteBtn")
        self.btn_delete.setToolTip("Xóa đơn hàng đã chọn")
        self.btn_delete.clicked.connect(self.delete_orders)
        toolbar_layout.addWidget(self.btn_delete)

        toolbar_layout.addSpacing(10)

        # Nút tra cứu
        self.btn_track_one = QPushButton("🔍 Tra cứu đơn")
        self.btn_track_one.setToolTip("Tra cứu đơn hàng đang chọn")
        self.btn_track_one.clicked.connect(self.track_selected_one)
        toolbar_layout.addWidget(self.btn_track_one)

        self.btn_track_selected = QPushButton("🔍 Tra cứu đã chọn")
        self.btn_track_selected.setToolTip("Tra cứu tất cả đơn hàng đã chọn")
        self.btn_track_selected.clicked.connect(self.track_selected_many)
        toolbar_layout.addWidget(self.btn_track_selected)

        self.btn_track_all = QPushButton("💖 Tra cứu tất cả")
        self.btn_track_all.setObjectName("primaryBtn")
        self.btn_track_all.setToolTip("Tra cứu tất cả đơn hàng trong bảng")
        self.btn_track_all.clicked.connect(self.track_all)
        toolbar_layout.addWidget(self.btn_track_all)

        toolbar_layout.addSpacing(10)

        # Nút nhập/xuất
        self.btn_import = QPushButton("📂 Nhập Excel/CSV")
        self.btn_import.clicked.connect(self.import_data)
        toolbar_layout.addWidget(self.btn_import)

        self.btn_export = QPushButton("💾 Xuất Excel/CSV")
        self.btn_export.clicked.connect(self.export_data)
        toolbar_layout.addWidget(self.btn_export)

        toolbar_layout.addStretch()

        # Menu phụ
        self.btn_more = QPushButton("⚙️")
        self.btn_more.setToolTip("Thêm tùy chọn & Sao lưu")
        more_menu = QMenu(self)
        more_menu.addAction("🌸 ➕ Thêm cột mới...", self.add_custom_column_dialog)
        more_menu.addAction("🗑️ Xóa cột tùy chọn...", self.delete_custom_column_dialog)
        more_menu.addSeparator()
        more_menu.addAction("📁 Mở thư mục dữ liệu", self.open_data_folder)
        more_menu.addAction("💾 Sao lưu dữ liệu", self.backup_data)
        more_menu.addAction("📥 Khôi phục dữ liệu", self.restore_data)
        more_menu.addSeparator()
        more_menu.addAction("ℹ️ Thông tin ứng dụng", self.show_about)
        self.btn_more.setMenu(more_menu)
        toolbar_layout.addWidget(self.btn_more)

        main_layout.addLayout(toolbar_layout)

        # ---- Tìm kiếm và lọc ----
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "🔍 Tìm theo tên acc, tên SP hoặc mã vận đơn...")
        self.search_edit.setMinimumWidth(320)
        self.search_edit.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_edit)

        lbl_carrier = QLabel("ĐVVC:")
        lbl_carrier.setStyleSheet("font-weight: bold; color: #D81B60;")
        filter_layout.addWidget(lbl_carrier)

        self.filter_carrier = QComboBox()
        self.filter_carrier.addItem("🌸 Tất cả ĐVVC", "ALL")
        self.filter_carrier.addItem("SPX - Shopee Express", CARRIER_SPX)
        self.filter_carrier.addItem("GHN - Giao Hàng Nhanh", CARRIER_GHN)
        self.filter_carrier.addItem("Chưa xác định", "UNKNOWN")
        self.filter_carrier.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_carrier)

        lbl_status = QLabel("Trạng thái:")
        lbl_status.setStyleSheet("font-weight: bold; color: #D81B60;")
        filter_layout.addWidget(lbl_status)

        self.filter_status = QComboBox()
        self.filter_status.addItem("🌸 Tất cả trạng thái", "")
        self.filter_status.addItem("Đã tra cứu", "has_status")
        self.filter_status.addItem("Chưa tra cứu", "no_status")
        self.filter_status.addItem("Có lỗi", "has_error")
        self.filter_status.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_status)

        # Nút sắp xếp theo hành trình trên thanh công cụ
        self.btn_sort_journey = QPushButton("🔃 Sắp xếp theo hành trình")
        self.btn_sort_journey.setCursor(Qt.PointingHandCursor)
        self.btn_sort_journey.setToolTip(
            "Nhấn để sắp xếp lại danh sách theo hành trình di chuyển:\n"
            "• Đơn thông thường / trung chuyển ở trên cùng\n"
            "• 'Đang giao hàng' ở kề cuối\n"
            "• 'Giao hàng thành công' ở cuối cùng\n"
            "• Cột STT luôn giữ từ 1 đến N liên tục"
        )
        self.btn_sort_journey.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF0F5, stop:1 #FFE4EC);
                color: #C2185B;
                border: 1.5px solid #FF8DA1;
                border-radius: 8px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFE4EC, stop:1 #FFCCD7);
                border-color: #D81B60;
                color: #880E4F;
            }
            QPushButton:pressed {
                background: #FFB6C1;
            }
        """)
        self.btn_sort_journey.clicked.connect(self.sort_by_journey)
        filter_layout.addWidget(self.btn_sort_journey)

        filter_layout.addStretch()

        self.count_label = QLabel("Tổng: 0 đơn")
        self.count_label.setStyleSheet("font-weight: bold; color: #D81B60; background: #FFE6EE; padding: 4px 12px; border-radius: 10px;")
        filter_layout.addWidget(self.count_label)

        main_layout.addLayout(filter_layout)

        # ---- Bảng dữ liệu ----
        self.table = QTableWidget()
        cols = self.COLUMNS
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        # Cho phép chỉnh sửa trực tiếp nội dung trên từng ô
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.EditKeyPressed |
            QAbstractItemView.AnyKeyPressed
        )
        self.table.doubleClicked.connect(self.on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemChanged.connect(self._on_cell_changed)

        # Ẩn vertical header mặc định: chỉ giữ lại 1 cột số thứ tự (cột STT màu vàng) và xóa bỏ vệt đen
        self.table.verticalHeader().setVisible(False)

        # Sử dụng header tùy biến để cột STT có nền vàng pastel, các cột khác có nền hồng pastel
        custom_header = PastelHeaderView(Qt.Horizontal, self.table)
        custom_header.setSortIndicatorShown(True)
        custom_header.sectionClicked.connect(self._on_header_section_clicked)
        self.table.setHorizontalHeader(custom_header)

        # Tạo nút Sắp xếp ngay tại tiêu đề cột Hành trình di chuyển
        self.btn_sort_in_header = QPushButton("🔃 Sắp xếp", custom_header)
        self.btn_sort_in_header.setCursor(Qt.PointingHandCursor)
        self.btn_sort_in_header.setToolTip(
            "Nhấn để sắp xếp lại thứ tự theo hành trình di chuyển:\n"
            "• Đơn thông thường / trung chuyển ở trên cùng\n"
            "• 'Đang giao hàng' ở kề cuối\n"
            "• 'Giao hàng thành công' ở cuối cùng\n"
            "• Cột STT luôn giữ từ 1 đến N liên tục"
        )
        self.btn_sort_in_header.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF5F8, stop:1 #FFE4EC);
                color: #C2185B;
                border: 1.5px solid #FF8DA1;
                border-radius: 11px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFE4EC, stop:1 #FFCCD7);
                border-color: #D81B60;
                color: #880E4F;
            }
            QPushButton:pressed {
                background-color: #FFB6C1;
            }
        """)
        self.btn_sort_in_header.clicked.connect(self.sort_by_journey)

        custom_header.sectionResized.connect(self._update_header_sort_button_geometry)
        custom_header.geometriesChanged.connect(self._update_header_sort_button_geometry)
        self.table.horizontalScrollBar().valueChanged.connect(self._update_header_sort_button_geometry)

        # Cài đặt kích thước các cột
        self._setup_column_widths()

        main_layout.addWidget(self.table)

        # ---- Khu vực thông báo ----
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "padding: 4px 10px; color: #C2185B; font-size: 12px; font-weight: 500;")
        main_layout.addWidget(self.status_label)

        # ---- Status bar ----
        self.statusBar().showMessage("✨ Sẵn sàng")

        # ---- Keyboard shortcuts ----
        QAction("Add", self, shortcut=QKeySequence("Ctrl+N"),
                triggered=self.add_order).setParent(self)
        QAction("Delete", self, shortcut=QKeySequence.Delete,
                triggered=self.delete_orders).setParent(self)
        QAction("Search", self, shortcut=QKeySequence("Ctrl+F"),
                triggered=self.focus_search).setParent(self)

        # ---- Style Sheet Toàn Diện: Hồng Pastel - Trắng Dễ Thương ----
        self.setStyleSheet("""
            /* Nền cửa sổ chính */
            QMainWindow, QWidget#centralWidget {
                background-color: #FFF5F8;
                color: #4A3B43;
                font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
            }

            /* Header phong cách Hello Kitty kết hợp Vàng Pastel */
            #headerWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFF8DC, stop:0.25 #FFEBF1, stop:0.75 #FFF0F5, stop:1 #FFF8DC);
                border-radius: 18px;
                border: 2px solid #FFE082;
            }
            #titleLabel {
                color: #D81B60;
                letter-spacing: 0.5px;
            }
            #subtitleLabel {
                color: #AD1457;
                font-style: italic;
            }

            /* Nút bấm thông thường (Trắng viền hồng pastel) */
            QPushButton {
                background-color: #FFFFFF;
                color: #C2185B;
                border: 1.5px solid #FFB6C1;
                border-radius: 13px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FFEAF0;
                border-color: #FF8DA1;
                color: #AD1457;
            }
            QPushButton:pressed {
                background-color: #FFD4DF;
            }
            QPushButton:disabled {
                background-color: #F8F4F6;
                color: #BDBDBD;
                border-color: #E0E0E0;
            }

            /* Nút nổi bật (Hồng pastel rực rỡ) */
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF94A8, stop:1 #FF6F89);
                color: #FFFFFF;
                border: 1.5px solid #FF5275;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFAAB9, stop:1 #FF839B);
            }
            QPushButton#primaryBtn:pressed {
                background: #E84366;
            }

            /* Nút xóa */
            QPushButton#deleteBtn:hover {
                background-color: #FFE5E5;
                border-color: #FF6B6B;
                color: #D32F2F;
            }

            /* Ô tìm kiếm */
            QLineEdit {
                background-color: #FFFFFF;
                color: #4A3B43;
                border: 1.5px solid #FFB6C1;
                border-radius: 13px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #FF6F89;
                background-color: #FFFFFF;
            }

            /* Hộp chọn Combobox */
            QComboBox {
                background-color: #FFFFFF;
                color: #4A3B43;
                border: 1.5px solid #FFB6C1;
                border-radius: 13px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #FF8DA1;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #4A3B43;
                selection-background-color: #FFE0E9;
                selection-color: #C2185B;
                border: 1.5px solid #FFB6C1;
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }

            /* Bảng dữ liệu */
            QTableWidget {
                background-color: #FFFFFF;
                color: #4A3B43;
                gridline-color: #FFE4EC;
                border: 1.5px solid #FFCCD5;
                border-radius: 14px;
                font-size: 12px;
                outline: none;
            }
            QTableWidget::item {
                padding: 6px 8px;
                color: #4A3B43;
                border-bottom: 1px solid #FFF0F4;
            }
            QTableWidget::item:alternate {
                background-color: #FFF8FA;
            }
            QTableWidget::item:selected {
                background-color: #FFD6E2;
                color: #880E4F;
                font-weight: bold;
            }

            /* Toàn bộ QHeaderView và góc bảng luôn có nền pastel, tuyệt đối không bị màu đen */
            QHeaderView {
                background-color: #FFF5F8;
                border: none;
            }
            QHeaderView::section {
                background-color: #FFF5F8;
                border: none;
            }
            QTableCornerButton::section {
                background: #FFF8DC;
                border: 1px solid #FFE082;
            }

            /* Thanh cuộn (Scrollbar) */
            QScrollBar:vertical {
                border: none;
                background: #FFF0F4;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #FFB3C2;
                min-height: 25px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #FF8DA1;
            }
            QScrollBar:horizontal {
                border: none;
                background: #FFF0F4;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #FFB3C2;
                min-width: 25px;
                border-radius: 5px;
            }
            QScrollBar::add-page, QScrollBar::sub-page {
                background: none;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                border: none;
                background: none;
                width: 0px;
                height: 0px;
            }

            /* Thanh tiến trình */
            QProgressBar {
                background-color: #FFE6EE;
                border: 1.5px solid #FFB6C1;
                border-radius: 8px;
                text-align: center;
                color: #880E4F;
                font-weight: bold;
                font-size: 11px;
                height: 18px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF94A8, stop:1 #FF5E7E);
                border-radius: 7px;
            }

            /* Menu chuột phải */
            QMenu {
                background-color: #FFFFFF;
                color: #4A3B43;
                border: 1.5px solid #FFB6C1;
                border-radius: 10px;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 22px;
                border-radius: 6px;
                color: #4A3B43;
            }
            QMenu::item:selected {
                background-color: #FFE4EC;
                color: #D81B60;
                font-weight: 600;
            }
            QMenu::separator {
                height: 1px;
                background: #FFD1DC;
                margin: 4px 8px;
            }

            /* Thanh trạng thái dưới cùng */
            QStatusBar {
                background-color: #FFE6EE;
                color: #880E4F;
                font-weight: 500;
                border-top: 1.5px solid #FFCCD5;
            }
        """)

    # ============================================================
    # Quản lý dữ liệu
    # ============================================================

    def load_data(self):
        """Tải dữ liệu từ database."""
        try:
            self.all_orders = self.db.get_all_orders()
            self.apply_filters()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải dữ liệu: {e}")

    def apply_filters(self):
        """Áp dụng bộ lọc và tìm kiếm."""
        orders = self.all_orders

        # Lọc theo carrier
        carrier_filter = self.filter_carrier.currentData()
        if carrier_filter == 'UNKNOWN':
            orders = [o for o in orders
                      if not o.get('carrier') or o['carrier'] == CARRIER_UNKNOWN]
        elif carrier_filter and carrier_filter != 'ALL':
            orders = [o for o in orders if o.get('carrier') == carrier_filter]

        # Lọc theo trạng thái
        status_filter = self.filter_status.currentData()
        if status_filter == 'has_status':
            orders = [o for o in orders if o.get('journey_status', '').strip()]
        elif status_filter == 'no_status':
            orders = [o for o in orders if not o.get('journey_status', '').strip()]
        elif status_filter == 'has_error':
            orders = [o for o in orders if o.get('last_error', '').strip()]

        # Tìm kiếm
        search = self.search_edit.text().strip().lower()
        if search:
            orders = [o for o in orders
                      if search in o.get('account_name', '').lower()
                      or search in o.get('product_name', '').lower()
                      or search in o.get('tracking_code', '').lower()]

        self.filtered_orders = orders
        if getattr(self, 'current_sort_column', -1) >= 0:
            self._sort_filtered_orders(self.current_sort_column, self.current_sort_order)
        self.refresh_table()

    def sort_by_journey(self):
        """Sắp xếp lại thứ tự danh sách đơn hàng theo hành trình di chuyển:
        - Đơn hàng thông thường / đang xử lý / trung chuyển ở trên cùng
        - 'Đang giao hàng' ở kề cuối
        - 'Giao hàng thành công' ở cuối cùng
        - Cột STT tự động đánh số liên tục từ 1 đến N
        """
        g0 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 0]
        g1 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 1]
        g2 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 2]

        g0.sort(key=lambda o: o.get('id', 0))
        g1.sort(key=lambda o: o.get('id', 0))
        g2.sort(key=lambda o: o.get('id', 0))

        self.filtered_orders = g0 + g1 + g2
        self.current_sort_column = self.COL_JOURNEY
        self.current_sort_order = Qt.AscendingOrder

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self.COL_JOURNEY, Qt.AscendingOrder)

        self.refresh_table()

        msg = f"✨ Đã sắp xếp theo hành trình: {len(g0)} đơn đang xử lý, {len(g1)} đang giao hàng, {len(g2)} đã giao thành công (STT 1..{len(self.filtered_orders)})"
        self.status_label.setText(msg)
        self.statusBar().showMessage(msg, 5000)

    @staticmethod
    def _get_status_priority(journey_status):
        """
        Quy tắc độ ưu tiên hành trình đơn hàng:
        - Nhóm 0: Đơn hàng bình thường / đang xử lý / đang trung chuyển / chưa tra cứu -> ở TRÊN CÙNG
        - Nhóm 1: 'Đang giao hàng' -> ĐẨY XUỐNG KỀ CUỐI
        - Nhóm 2: 'Giao hàng thành công' -> ĐẨY XUỐNG CUỐI CÙNG
        """
        if not journey_status:
            return 0
        s = str(journey_status).strip().lower()
        if any(w in s for w in ["giao hàng thành công", "giao thành công", "đã giao thành công", "đã giao"]):
            return 2
        if any(w in s for w in ["đang giao hàng", "đang giao", "nhân viên đang giao", "đang đi giao"]):
            return 1
        return 0

    def _sort_filtered_orders(self, logical_index, sort_order):
        """Sắp xếp danh sách filtered_orders theo cột đã chọn, đồng thời luôn tuân thủ:
        - Đơn hàng thông thường ở trên
        - 'Đang giao hàng' luôn ở kề cuối
        - 'Giao hàng thành công' luôn ở cuối cùng
        """
        reverse = (sort_order == Qt.DescendingOrder)

        def get_col_key(order):
            if logical_index == 0:  # STT: sắp xếp theo ID gốc
                return order.get('id', 0)
            elif logical_index == 1:  # Tên acc đặt
                return (order.get('account_name') or '').lower()
            elif logical_index == 2:  # Tên SP
                return (order.get('product_name') or '').lower()
            elif logical_index == 3:  # Mã vận đơn
                return (order.get('tracking_code') or '').lower()
            elif logical_index == 4:  # Hành trình di chuyển
                return (order.get('journey_status') or '').lower()
            elif logical_index == 5:  # Số tiền: sắp xếp theo giá trị số thực tế
                return order.get('amount') or 0.0
            elif logical_index == 6:  # Địa chỉ
                return (order.get('address') or '').lower()
            elif logical_index >= 7:  # Cột tùy biến
                header_item = self.table.horizontalHeaderItem(logical_index)
                if header_item:
                    col_name = header_item.text()
                    extra = order.get('extra_data') or '{}'
                    if isinstance(extra, str):
                        try:
                            import json
                            extra_dict = json.loads(extra)
                        except Exception:
                            extra_dict = {}
                    else:
                        extra_dict = extra or {}
                    return str(extra_dict.get(col_name, '')).lower()
                return ''
            return ''

        # Tách thành 3 nhóm theo yêu cầu:
        # Nhóm 0: Đơn thông thường
        # Nhóm 1: 'Đang giao hàng' (kề cuối)
        # Nhóm 2: 'Giao hàng thành công' (cuối cùng)
        group_0 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 0]
        group_1 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 1]
        group_2 = [o for o in self.filtered_orders if self._get_status_priority(o.get('journey_status', '')) == 2]

        group_0.sort(key=get_col_key, reverse=reverse)
        group_1.sort(key=get_col_key, reverse=reverse)
        group_2.sort(key=get_col_key, reverse=reverse)

        self.filtered_orders = group_0 + group_1 + group_2

    def _on_header_section_clicked(self, logical_index):
        """
        Sắp xếp danh sách đơn hàng khi bấm vào tiêu đề bất kỳ cột nào.
        Đặc biệt: Cột STT luôn giữ cố định số thứ tự từ 1 đến lớn nhất, không bị xáo trộn.
        """
        if logical_index == self.COL_JOURNEY:
            self.sort_by_journey()
            return
        if logical_index == self.current_sort_column:
            if self.current_sort_order == Qt.AscendingOrder:
                self.current_sort_order = Qt.DescendingOrder
            else:
                self.current_sort_order = Qt.AscendingOrder
        else:
            self.current_sort_column = logical_index
            self.current_sort_order = Qt.AscendingOrder

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self.current_sort_column, self.current_sort_order)

        self._sort_filtered_orders(self.current_sort_column, self.current_sort_order)
        self.refresh_table()

        header_item = self.table.horizontalHeaderItem(logical_index)
        col_name = header_item.text() if header_item else ""
        direction_text = "tăng dần" if self.current_sort_order == Qt.AscendingOrder else "giảm dần"
        self.statusBar().showMessage(
            f"✨ Đã sắp xếp theo '{col_name}' ({direction_text}) - STT giữ nguyên từ 1 đến {len(self.filtered_orders)}",
            2500
        )

    def _renumber_stt(self):
        """Đảm bảo cột STT luôn hiển thị liên tục từ 1 đến số dòng lớn nhất."""
        self._loading_data = True
        for r in range(self.table.rowCount()):
            stt_item = self.table.item(r, 0)
            if stt_item:
                stt_item.setData(Qt.DisplayRole, r + 1)
        self._loading_data = False

    def _setup_column_widths(self):
        """Thiết lập chế độ co giãn và độ rộng các cột."""
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)       # STT
        header.setSectionResizeMode(1, QHeaderView.Interactive) # Tên acc
        header.setSectionResizeMode(2, QHeaderView.Interactive) # Tên SP
        header.setSectionResizeMode(3, QHeaderView.Interactive) # Mã vận đơn
        header.setSectionResizeMode(4, QHeaderView.Stretch)     # Hành trình
        header.setSectionResizeMode(5, QHeaderView.Interactive) # Số tiền
        if self.table.columnCount() > 6:
            header.setSectionResizeMode(6, QHeaderView.Interactive) # Địa chỉ

        for c in range(7, self.table.columnCount()):
            header.setSectionResizeMode(c, QHeaderView.Interactive) # Cột tùy chọn

        self.table.setColumnWidth(0, 58)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 180)
        self.table.setColumnWidth(5, 160)
        if self.table.columnCount() > 6:
            self.table.setColumnWidth(6, 140)
        for c in range(7, self.table.columnCount()):
            self.table.setColumnWidth(c, 140)

        self._update_header_sort_button_geometry()

    def refresh_table(self):
        """Cập nhật bảng hiển thị."""
        self._loading_data = True
        self.table.setSortingEnabled(False)

        cols = self.COLUMNS
        if self.table.columnCount() != len(cols):
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self._setup_column_widths()

        self.table.setRowCount(len(self.filtered_orders))

        for row, order in enumerate(self.filtered_orders):
            # STT - 1 cột duy nhất nền Vàng Pastel, chữ nâu ấm (không sửa STT)
            stt_item = QTableWidgetItem()
            stt_item.setData(Qt.DisplayRole, row + 1)
            stt_item.setTextAlignment(Qt.AlignCenter)
            stt_item.setData(Qt.UserRole, order['id'])  # Lưu ID ẩn
            stt_item.setBackground(QColor('#FFFDE7'))
            stt_item.setForeground(QColor('#795548'))
            font_stt = stt_item.font()
            font_stt.setBold(True)
            stt_item.setFont(font_stt)
            stt_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, stt_item)

            # Tên acc đặt
            acc_item = QTableWidgetItem(order.get('account_name', ''))
            acc_item.setForeground(QColor('#4A3B43'))
            self.table.setItem(row, 1, acc_item)

            # Tên SP
            prod_item = QTableWidgetItem(order.get('product_name', ''))
            prod_item.setForeground(QColor('#4A3B43'))
            self.table.setItem(row, 2, prod_item)

            # Mã vận đơn
            tracking_item = QTableWidgetItem(order.get('tracking_code', ''))
            carrier = order.get('carrier', '')
            if carrier == CARRIER_SPX:
                tracking_item.setForeground(QColor('#D32F2F'))
            elif carrier == CARRIER_GHN:
                tracking_item.setForeground(QColor('#2E7D32'))
            else:
                tracking_item.setForeground(QColor('#4A3B43'))
            self.table.setItem(row, 3, tracking_item)

            # Hành trình di chuyển
            journey = order.get('journey_status', '')
            journey_item = QTableWidgetItem(journey)
            journey_item.setForeground(QColor('#4A3B43'))
            if journey:
                journey_item.setToolTip(
                    f"Trạng thái: {journey}\n"
                    f"Tra cứu lúc: {order.get('last_query_time', 'N/A')}")
            if order.get('last_error'):
                journey_item.setToolTip(
                    (journey_item.toolTip() or '') +
                    f"\n⚠️ Lỗi: {order['last_error']}")
            self.table.setItem(row, 4, journey_item)

            # Số tiền cần thanh toán
            amount_text = order.get('amount_text', '')
            if not amount_text and order.get('amount', 0):
                amount_text = format_amount(order['amount'])
            amount_item = QTableWidgetItem(amount_text)
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setForeground(QColor('#AD1457'))
            font_amt = amount_item.font()
            font_amt.setBold(True)
            amount_item.setFont(font_amt)
            self.table.setItem(row, 5, amount_item)

            # Cột 7: Địa chỉ (tùy chọn Bình Định / Quy Nhơn)
            curr_addr = order.get('address', '')
            addr_item = QTableWidgetItem(curr_addr)
            addr_item.setForeground(QColor('#4A3B43'))
            self.table.setItem(row, 6, addr_item)

            addr_combo = QComboBox()
            addr_combo.addItem("")
            addr_combo.addItem("Bình Định")
            addr_combo.addItem("Quy Nhơn")
            idx = addr_combo.findText(curr_addr)
            if idx >= 0:
                addr_combo.setCurrentIndex(idx)
            elif curr_addr:
                addr_combo.addItem(curr_addr)
                addr_combo.setCurrentText(curr_addr)

            addr_combo.setStyleSheet("""
                QComboBox {
                    background-color: #FFFFFF;
                    color: #4A3B43;
                    border: 1px solid #FFCCD5;
                    border-radius: 8px;
                    padding: 2px 6px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QComboBox:hover {
                    border-color: #FF8DA1;
                    background-color: #FFF8FA;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 16px;
                }
                QComboBox QAbstractItemView {
                    background-color: #FFFFFF;
                    color: #4A3B43;
                    selection-background-color: #FFE0E9;
                    selection-color: #C2185B;
                    border: 1.5px solid #FFB6C1;
                    border-radius: 8px;
                }
            """)
            addr_combo.currentTextChanged.connect(
                lambda text, oid=order['id']: self._on_address_changed(oid, text)
            )
            self.table.setCellWidget(row, 6, addr_combo)

            # Các cột tùy biến (Custom Columns) từ vị trí 7 trở đi
            extra_data = order.get('extra_data') or '{}'
            if isinstance(extra_data, str):
                try:
                    import json
                    extra_dict = json.loads(extra_data)
                except Exception:
                    extra_dict = {}
            else:
                extra_dict = extra_data or {}

            for c_idx, c_name in enumerate(self.custom_columns, start=7):
                val = extra_dict.get(c_name, '')
                c_item = QTableWidgetItem(str(val))
                c_item.setForeground(QColor('#4A3B43'))
                self.table.setItem(row, c_idx, c_item)

        self.table.setSortingEnabled(False)
        self._loading_data = False

        # Cập nhật số lượng
        total = len(self.all_orders)
        showing = len(self.filtered_orders)
        if showing != total:
            self.count_label.setText(f"Hiển thị: {showing}/{total} đơn")
        else:
            self.count_label.setText(f"Tổng: {total} đơn")

        self._update_header_sort_button_geometry()

    def get_selected_order_ids(self):
        """Lấy danh sách ID đơn hàng đã chọn."""
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())

        order_ids = []
        for row in sorted(rows):
            stt_item = self.table.item(row, 0)
            if stt_item:
                order_id = stt_item.data(Qt.UserRole)
                if order_id:
                    order_ids.append(order_id)
        return order_ids

    def get_order_by_id(self, order_id):
        """Tìm order trong danh sách theo ID."""
        for order in self.all_orders:
            if order['id'] == order_id:
                return order
        return None

    # ============================================================
    # Thao tác CRUD
    # ============================================================

    def add_order(self):
        """Thêm đơn hàng mới."""
        dialog = OrderDialog(self, db=self.db)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                # Tự động thêm ngày tạo đơn vào sau tên sản phẩm nếu chưa có
                if data.get('product_name'):
                    data['product_name'] = append_created_date_to_product(data['product_name'])
                self.db.add_order(**data)
                self.load_data()
                self.status_label.setText("✅ Đã thêm đơn hàng mới")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể thêm đơn hàng: {e}")

    def edit_order(self):
        """Sửa đơn hàng đã chọn."""
        ids = self.get_selected_order_ids()
        if not ids:
            QMessageBox.information(self, "Thông báo",
                                    "Vui lòng chọn đơn hàng cần sửa.")
            return
        if len(ids) > 1:
            QMessageBox.information(self, "Thông báo",
                                    "Chỉ có thể sửa một đơn hàng mỗi lần.")
            return

        order = self.db.get_order(ids[0])
        if not order:
            return

        dialog = OrderDialog(self, order=order, db=self.db)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                if data.get('product_name'):
                    # Giữ nguyên ngày tạo gốc của đơn hàng (không bao giờ thay đổi)
                    data['product_name'] = append_created_date_to_product(
                        data['product_name'], order.get('created_at')
                    )
                self.db.update_order(ids[0], **data)
                self.load_data()
                self.status_label.setText("✅ Đã cập nhật đơn hàng")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi",
                                     f"Không thể cập nhật: {e}")

    def delete_orders(self):
        """Xóa đơn hàng đã chọn."""
        ids = self.get_selected_order_ids()
        if not ids:
            QMessageBox.information(self, "Thông báo",
                                    "Vui lòng chọn đơn hàng cần xóa.")
            return

        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa {len(ids)} đơn hàng đã chọn?\n"
            "Thao tác này không thể hoàn tác.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_orders(ids)
                self.load_data()
                self.status_label.setText(
                    f"✅ Đã xóa {len(ids)} đơn hàng")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa: {e}")

    def on_double_click(self, index):
        """Xem chi tiết khi double-click vào cột STT (các cột khác để người dùng gõ trực tiếp)."""
        if index.column() == 0:
            row = index.row()
            stt_item = self.table.item(row, 0)
            if stt_item:
                order_id = stt_item.data(Qt.UserRole)
                order = self.db.get_order(order_id)
                if order:
                    dialog = OrderDetailDialog(self, order=order)
                    dialog.exec()

    def show_context_menu(self, pos):
        """Menu chuột phải."""
        menu = QMenu(self)
        menu.addAction("✨ ➕ Thêm dòng mới", self.add_quick_row)
        menu.addAction("🌸 ➕ Thêm cột mới...", self.add_custom_column_dialog)
        menu.addSeparator()
        menu.addAction("✏️ Sửa", self.edit_order)
        menu.addAction("🗑️ Xóa", self.delete_orders)
        menu.addSeparator()
        menu.addAction("🔍 Tra cứu đơn này", self.track_selected_one)
        menu.addAction("📋 Xem chi tiết", self._view_detail_context)
        menu.addSeparator()

        # Mở trang tra cứu
        ids = self.get_selected_order_ids()
        if ids:
            order = self.get_order_by_id(ids[0])
            if order and order.get('tracking_code') and order.get('carrier'):
                menu.addAction("🌐 Mở trang tra cứu",
                               lambda: self._open_tracking(order))

        menu.addSeparator()
        menu_sort = menu.addMenu("🔄 Sắp xếp bảng")
        menu_sort.addAction("Theo Hành trình di chuyển", lambda: self._on_header_section_clicked(4))
        menu_sort.addAction("Theo Mã vận đơn", lambda: self._on_header_section_clicked(3))
        menu_sort.addAction("Theo Tên sản phẩm", lambda: self._on_header_section_clicked(2))
        menu_sort.addAction("Theo Tên người đặt", lambda: self._on_header_section_clicked(1))
        menu_sort.addAction("Theo Số tiền thanh toán", lambda: self._on_header_section_clicked(5))
        menu_sort.addAction("Theo Địa chỉ", lambda: self._on_header_section_clicked(6))
        menu_sort.addSeparator()
        menu_sort.addAction("Khôi phục thứ tự ban đầu", lambda: self._on_header_section_clicked(0))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_cell_changed(self, item):
        """Xử lý chỉnh sửa trực tiếp nội dung trong từng ô của bảng."""
        if getattr(self, '_loading_data', False):
            return

        row = item.row()
        col = item.column()

        stt_item = self.table.item(row, 0)
        if not stt_item:
            return
        order_id = stt_item.data(Qt.UserRole)
        if not order_id:
            return

        new_text = item.text().strip()

        try:
            if col == 1:  # Tên acc đặt
                self.db.update_order(order_id, account_name=new_text)
                self._update_order_cache(order_id, 'account_name', new_text)
            elif col == 2:  # Tên SP
                order = next((o for o in self.all_orders if o.get('id') == order_id), None)
                if not order:
                    order = self.db.get_order(order_id)
                created_at = order.get('created_at') if order else None
                final_name = append_created_date_to_product(new_text, created_at)
                if final_name != new_text:
                    self._loading_data = True
                    item.setText(final_name)
                    self._loading_data = False
                    new_text = final_name
                self.db.update_order(order_id, product_name=new_text)
                self._update_order_cache(order_id, 'product_name', new_text)
            elif col == 3:  # Mã vận đơn
                carrier = detect_carrier(new_text)
                if carrier == CARRIER_UNKNOWN and new_text:
                    carrier = CARRIER_GHN
                self.db.update_order(order_id, tracking_code=new_text, carrier=carrier)
                self._update_order_cache(order_id, 'tracking_code', new_text)
                self._update_order_cache(order_id, 'carrier', carrier)
                if carrier == CARRIER_SPX:
                    item.setForeground(QColor('#E57373'))
                elif carrier == CARRIER_GHN:
                    item.setForeground(QColor('#43A047'))
                else:
                    item.setForeground(QColor('#8C4A60'))
            elif col == 4:  # Hành trình di chuyển
                self.db.update_order(order_id, journey_status=new_text)
                self._update_order_cache(order_id, 'journey_status', new_text)
            elif col == 5:  # Số tiền cần thanh toán
                amt = parse_amount(new_text)
                amt_text = format_amount(amt) if amt else new_text
                self.db.update_order(order_id, amount=amt, amount_text=amt_text)
                self._update_order_cache(order_id, 'amount', amt)
                self._update_order_cache(order_id, 'amount_text', amt_text)
                self._loading_data = True
                item.setText(amt_text)
                self._loading_data = False
            elif col == 6:  # Địa chỉ
                self.db.update_order(order_id, address=new_text)
                self._update_order_cache(order_id, 'address', new_text)
            elif col >= 7:  # Cột tùy chọn
                header_item = self.table.horizontalHeaderItem(col)
                if header_item:
                    col_name = header_item.text()
                    self.db.update_order_extra(order_id, col_name, new_text)
                    self._update_order_cache_extra(order_id, col_name, new_text)

            self.statusBar().showMessage("✨ Đã lưu thay đổi", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"⚠️ Lỗi lưu dữ liệu: {e}", 3000)

    def _on_address_changed(self, order_id, new_address):
        """Cập nhật địa chỉ khi người dùng chọn trong combobox."""
        if getattr(self, '_loading_data', False):
            return
        new_address = new_address.strip()
        try:
            self.db.update_order(order_id, address=new_address)
            self._update_order_cache(order_id, 'address', new_address)
            # Cập nhật text trong item của cột 6
            for r in range(self.table.rowCount()):
                stt = self.table.item(r, 0)
                if stt and stt.data(Qt.UserRole) == order_id:
                    it = self.table.item(r, 6)
                    if it and it.text() != new_address:
                        self._loading_data = True
                        it.setText(new_address)
                        self._loading_data = False
                    break
            self.statusBar().showMessage(f"✨ Đã cập nhật địa chỉ: {new_address or 'Trống'}", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"⚠️ Lỗi cập nhật địa chỉ: {e}", 3000)

    def _update_order_cache(self, order_id, field, value):
        for o in self.all_orders:
            if o['id'] == order_id:
                o[field] = value
                break
        for o in self.filtered_orders:
            if o['id'] == order_id:
                o[field] = value
                break

    def _update_order_cache_extra(self, order_id, col_name, value):
        import json
        for o in self.all_orders + self.filtered_orders:
            if o['id'] == order_id:
                extra = o.get('extra_data') or '{}'
                if isinstance(extra, str):
                    try:
                        extra_dict = json.loads(extra)
                    except Exception:
                        extra_dict = {}
                else:
                    extra_dict = extra or {}
                extra_dict[col_name] = value
                o['extra_data'] = extra_dict

    def add_quick_row(self):
        """Thêm 1 dòng trống mới trực tiếp vào bảng để người dùng gõ ngay."""
        try:
            new_id = self.db.add_order()
            self.load_data()
            row_count = self.table.rowCount()
            if row_count > 0:
                self.table.setCurrentCell(row_count - 1, 1)
                item = self.table.item(row_count - 1, 1)
                if item:
                    self.table.editItem(item)
            self.statusBar().showMessage("✨ Đã thêm dòng mới! Hãy gõ thông tin trực tiếp vào ô.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm dòng mới: {e}")

    def add_custom_column_dialog(self):
        """Hộp thoại thêm cột tùy chọn mới."""
        from PySide6.QtWidgets import QInputDialog
        col_name, ok = QInputDialog.getText(
            self, "🌸 Thêm cột mới",
            "Nhập tên cột bạn muốn thêm vào bảng:\n(Ví dụ: Ghi chú, SĐT người nhận, Ngày nhận, v.v.)"
        )
        if not ok or not col_name.strip():
            return
        col_name = col_name.strip()
        existing = self.COLUMNS
        if col_name in existing:
            QMessageBox.warning(self, "Cột đã tồn tại", f"Cột '{col_name}' đã có trong bảng!")
            return

        try:
            self.db.add_custom_column(col_name)
            self.custom_columns.append(col_name)
            self.refresh_table()
            self.statusBar().showMessage(f"✨ Đã thêm cột '{col_name}' thành công!", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm cột: {e}")

    def delete_custom_column_dialog(self):
        """Hộp thoại xóa cột tùy chọn."""
        if not self.custom_columns:
            QMessageBox.information(self, "Thông báo", "Chưa có cột tùy chọn nào để xóa.")
            return

        from PySide6.QtWidgets import QInputDialog
        col_name, ok = QInputDialog.getItem(
            self, "🗑️ Xóa cột tùy chọn",
            "Chọn cột bạn muốn xóa khỏi bảng:",
            self.custom_columns, 0, False
        )
        if not ok or not col_name:
            return

        confirm = QMessageBox.question(
            self, "Xác nhận xóa cột",
            f"Bạn có chắc muốn xóa cột '{col_name}'?\nDữ liệu trong cột này sẽ bị gỡ bỏ khỏi bảng.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                self.db.delete_custom_column(col_name)
                self.custom_columns.remove(col_name)
                self.refresh_table()
                self.statusBar().showMessage(f"🗑️ Đã xóa cột '{col_name}'", 4000)
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa cột: {e}")

    def _view_detail_context(self):
        """Xem chi tiết từ context menu."""
        ids = self.get_selected_order_ids()
        if ids:
            order = self.db.get_order(ids[0])
            if order:
                dialog = OrderDetailDialog(self, order=order)
                dialog.exec()

    def _open_tracking(self, order):
        """Mở trang tra cứu trong trình duyệt."""
        from .tracking import open_tracking_url
        open_tracking_url(order['tracking_code'], order['carrier'])

    # ============================================================
    # Tra cứu vận đơn
    # ============================================================

    def _prepare_tracking_list(self, order_ids):
        """Chuẩn bị danh sách đơn hàng để tra cứu."""
        orders_to_track = []
        errors = []

        for oid in order_ids:
            order = self.get_order_by_id(oid)
            if not order:
                continue

            tracking = order.get('tracking_code', '').strip()
            if not tracking:
                errors.append(f"Đơn #{oid}: Chưa có mã vận đơn")
                continue

            carrier = order.get('carrier', '')
            if not carrier or carrier == CARRIER_UNKNOWN:
                carrier = detect_carrier(tracking)
                if carrier == CARRIER_UNKNOWN:
                    carrier = CARRIER_GHN
                self.db.update_order(oid, carrier=carrier)
                self._update_order_cache(oid, 'carrier', carrier)

            phone_last4 = str(order.get('phone_last4', '') or '').strip()
            if carrier == CARRIER_GHN and not phone_last4:
                from PySide6.QtWidgets import QInputDialog
                phone_input, ok = QInputDialog.getText(
                    self,
                    "Tra cứu Giao Hàng Nhanh (GHN)",
                    f"Đơn hàng GHN mã: {tracking}\n\n"
                    f"Trang Giao Hàng Nhanh bắt buộc cần Số điện thoại hoặc 4 số cuối SĐT\n"
                    f"của người nhận hoặc người gửi để tra cứu.\n\n"
                    f"Vui lòng nhập SĐT hoặc 4 số cuối:",
                    QLineEdit.Normal,
                    ""
                )
                if ok and phone_input.strip():
                    phone_last4 = phone_input.strip()
                    self.db.update_order(oid, phone_last4=phone_last4)
                    self._update_order_cache(oid, 'phone_last4', phone_last4)
                else:
                    from .tracking import open_tracking_url
                    reply = QMessageBox.question(
                        self,
                        "Tra cứu GHN",
                        f"Đơn hàng GHN {tracking} chưa có số điện thoại nên không thể tự động tra cứu ngầm.\n\n"
                        f"Bạn có muốn mở trang web GHN trên trình duyệt để tự tra cứu không?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        open_tracking_url(tracking, CARRIER_GHN)
                    continue

            existing_status = str(order.get('journey_status', '') or '').strip()
            existing_detail = str(order.get('journey_detail', '') or '').strip()
            orders_to_track.append((oid, tracking, carrier, phone_last4, existing_status, existing_detail))

        return orders_to_track, errors

    def _start_tracking(self, orders_to_track, errors=None):
        """Bắt đầu tra cứu."""
        if not orders_to_track:
            error_msg = "Không có đơn hàng nào có thể tra cứu."
            if errors:
                error_msg += "\n\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Thông báo", error_msg)
            return

        # Hiển thị lỗi chuẩn bị nếu có
        if errors:
            self.status_label.setText(
                f"⚠️ {len(errors)} đơn bị bỏ qua. "
                f"Đang tra cứu {len(orders_to_track)} đơn...")

        # Disable buttons
        self._set_tracking_ui(True)

        self.tracking_worker = TrackingWorker(orders_to_track)
        self.tracking_worker.progress.connect(self._on_tracking_progress)
        self.tracking_worker.result.connect(self._on_tracking_result)
        self.tracking_worker.finished_all.connect(self._on_tracking_finished)
        self.tracking_worker.start()

    def track_selected_one(self):
        """Tra cứu một đơn hàng đang chọn."""
        ids = self.get_selected_order_ids()
        if not ids:
            QMessageBox.information(self, "Thông báo",
                                    "Vui lòng chọn đơn hàng cần tra cứu.")
            return

        orders_to_track, errors = self._prepare_tracking_list([ids[0]])
        self._start_tracking(orders_to_track, errors)

    def track_selected_many(self):
        """Tra cứu nhiều đơn hàng đã chọn."""
        ids = self.get_selected_order_ids()
        if not ids:
            QMessageBox.information(self, "Thông báo",
                                    "Vui lòng chọn đơn hàng cần tra cứu.")
            return

        orders_to_track, errors = self._prepare_tracking_list(ids)
        self._start_tracking(orders_to_track, errors)

    def track_all(self):
        """Tra cứu tất cả đơn hàng."""
        if not self.filtered_orders:
            QMessageBox.information(self, "Thông báo",
                                    "Không có đơn hàng nào để tra cứu.")
            return

        reply = QMessageBox.question(
            self, "Xác nhận",
            f"Tra cứu tất cả {len(self.filtered_orders)} đơn hàng?\n"
            "Quá trình có thể mất vài phút.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        all_ids = [o['id'] for o in self.filtered_orders]
        orders_to_track, errors = self._prepare_tracking_list(all_ids)
        self._start_tracking(orders_to_track, errors)

    def _set_tracking_ui(self, tracking):
        """Bật/tắt UI khi đang tra cứu."""
        self.progress_bar.setVisible(tracking)
        self.btn_track_one.setEnabled(not tracking)
        self.btn_track_selected.setEnabled(not tracking)
        self.btn_track_all.setEnabled(not tracking)

    def _on_tracking_progress(self, current, total, message):
        """Cập nhật tiến trình tra cứu."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total}")
        self.status_label.setText(message)

    def _on_tracking_result(self, order_id, success, status, detail, error):
        """Nhận kết quả tra cứu từng đơn."""
        try:
            if success:
                self.db.update_journey(order_id, status, detail)
            else:
                self.db.update_query_error(order_id, error)
        except Exception as e:
            print(f"Error updating order {order_id}: {e}")

        # Cập nhật dữ liệu trong bộ nhớ - GIỮ NGUYÊN VỊ TRÍ, TUYỆT ĐỐI KHÔNG TỰ ĐỘNG SẮP XẾP LẠI
        for order in self.all_orders:
            if order['id'] == order_id:
                if success:
                    order['journey_status'] = status
                    order['journey_detail'] = detail
                    order['last_error'] = ''
                else:
                    order['last_error'] = error
                break

        for order in self.filtered_orders:
            if order['id'] == order_id:
                if success:
                    order['journey_status'] = status
                    order['journey_detail'] = detail
                    order['last_error'] = ''
                else:
                    order['last_error'] = error
                break

        # Cập nhật trực tiếp nội dung ô tại đúng hàng đó mà KHÔNG làm thay đổi vị trí
        self._update_table_row_for_order(order_id)

    def _update_table_row_for_order(self, order_id):
        """Cập nhật nội dung hiển thị của 1 đơn hàng tại đúng hàng đó mà KHÔNG thay đổi vị trí."""
        self._loading_data = True
        try:
            for row in range(self.table.rowCount()):
                stt_item = self.table.item(row, 0)
                if stt_item and stt_item.data(Qt.UserRole) == order_id:
                    order = None
                    for o in self.filtered_orders:
                        if o['id'] == order_id:
                            order = o
                            break
                    if not order:
                        return

                    # Cập nhật ô Hành trình di chuyển (cột 4)
                    journey = order.get('journey_status', '')
                    journey_item = self.table.item(row, self.COL_JOURNEY)
                    if not journey_item:
                        journey_item = QTableWidgetItem(journey)
                        self.table.setItem(row, self.COL_JOURNEY, journey_item)
                    else:
                        journey_item.setText(journey)

                    journey_item.setForeground(QColor('#4A3B43'))
                    tooltip = ""
                    if journey:
                        tooltip = (f"Trạng thái: {journey}\n"
                                   f"Tra cứu lúc: {order.get('last_query_time', 'N/A')}")
                    if order.get('last_error'):
                        tooltip = (tooltip + "\n" if tooltip else "") + f"⚠️ Lỗi: {order['last_error']}"
                    journey_item.setToolTip(tooltip)

                    # Cập nhật màu mã vận đơn theo đơn vị vận chuyển (cột 3)
                    tracking_item = self.table.item(row, self.COL_TRACKING)
                    if tracking_item:
                        carrier = order.get('carrier', '')
                        if carrier == CARRIER_SPX:
                            tracking_item.setForeground(QColor('#D32F2F'))
                        elif carrier == CARRIER_GHN:
                            tracking_item.setForeground(QColor('#2E7D32'))
                        else:
                            tracking_item.setForeground(QColor('#4A3B43'))
                    break
        finally:
            self._loading_data = False

    def _on_tracking_finished(self, success_count, fail_count):
        """Kết thúc tra cứu."""
        self._set_tracking_ui(False)
        # Giữ nguyên vị trí các đơn hàng sau khi tra cứu xong, KHÔNG gọi load_data() gây xáo trộn

        if fail_count > 0:
            msg = f"⚠️ Tra cứu xong: {success_count} thành công, {fail_count} thất bại"
            self.status_label.setText(msg)
            self.statusBar().showMessage(msg, 5000)

            # Chỉ hiện cửa sổ thông báo khi có đơn hàng bị thất bại
            QMessageBox.warning(
                self, "Kết quả tra cứu có lỗi",
                f"Đã hoàn tất tra cứu:\n"
                f"• Thành công: {success_count}\n"
                f"• Thất bại: {fail_count}\n\n"
                f"Xem chi tiết lỗi bằng cách double-click vào đơn hàng."
            )
        else:
            # Tra cứu thành công: Cập nhật trực tiếp lên cột hành trình, không hiện hộp thoại
            msg = f"✨ Tra cứu thành công {success_count} đơn hàng!"
            self.status_label.setText(msg)
            self.statusBar().showMessage(msg, 5000)

    # ============================================================
    # Tìm kiếm và lọc
    # ============================================================

    def on_search_changed(self, text):
        """Xử lý khi thay đổi ô tìm kiếm."""
        self.apply_filters()

    def on_filter_changed(self):
        """Xử lý khi thay đổi bộ lọc."""
        self.apply_filters()

    def focus_search(self):
        """Focus vào ô tìm kiếm."""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # ============================================================
    # Nhập/Xuất dữ liệu
    # ============================================================

    def import_data(self):
        """Nhập dữ liệu từ Excel/CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file nhập dữ liệu", "",
            "Excel/CSV Files (*.xlsx *.csv);;Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            orders, warnings = import_file(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi nhập dữ liệu", str(e))
            return

        if not orders:
            QMessageBox.information(self, "Thông báo",
                                    "Không tìm thấy dữ liệu trong file.")
            return

        # Kiểm tra trùng mã vận đơn
        existing_codes = {o['tracking_code']
                          for o in self.all_orders if o.get('tracking_code')}
        new_codes = [o['tracking_code'] for o in orders if o.get('tracking_code')]
        duplicate_codes = [c for c in new_codes if c in existing_codes]

        # Hiện dialog xác nhận
        dialog = ImportDialog(self, len(orders), duplicate_codes)
        if dialog.exec() != QDialog.Accepted:
            return

        mode = dialog.get_mode()

        try:
            if mode == 'replace':
                # Xóa tất cả rồi thêm mới
                reply = QMessageBox.warning(
                    self, "Cảnh báo",
                    "Thay thế sẽ XÓA TOÀN BỘ dữ liệu hiện tại.\n"
                    "Bạn có chắc chắn?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

                for old_order in self.all_orders:
                    self.db.delete_order(old_order['id'])

            added = 0
            for order_data in orders:
                carrier = detect_carrier(order_data.get('tracking_code', ''))
                prod_name = append_created_date_to_product(order_data.get('product_name', ''))
                self.db.add_order(
                    account_name=order_data.get('account_name', ''),
                    product_name=prod_name,
                    tracking_code=order_data.get('tracking_code', ''),
                    carrier=carrier,
                    amount=order_data.get('amount', 0),
                    amount_text=order_data.get('amount_text', ''),
                    address=order_data.get('address', ''),
                )
                added += 1

            self.load_data()

            msg = f"✅ Đã nhập {added} đơn hàng"
            if warnings:
                msg += f"\n⚠️ Cảnh báo:\n" + "\n".join(warnings[:5])
            self.status_label.setText(msg)
            QMessageBox.information(self, "Nhập dữ liệu", msg)

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi nhập dữ liệu: {e}")

    def export_data(self):
        """Xuất dữ liệu ra Excel/CSV."""
        if not self.filtered_orders:
            QMessageBox.information(self, "Thông báo",
                                    "Không có dữ liệu để xuất.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Xuất dữ liệu", "don_hang",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.csv'):
                export_csv(file_path, self.filtered_orders, custom_columns=self.custom_columns)
            else:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                export_excel(file_path, self.filtered_orders, custom_columns=self.custom_columns)

            self.status_label.setText(f"✅ Đã xuất dữ liệu: {file_path}")
            QMessageBox.information(self, "Xuất dữ liệu",
                                    f"Đã xuất thành công!\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất",
                                 f"Không thể xuất dữ liệu: {e}")

    # ============================================================
    # Sao lưu / Khôi phục
    # ============================================================

    def backup_data(self):
        """Sao lưu cơ sở dữ liệu."""
        try:
            path = self.db.backup_database()
            self.status_label.setText(f"✅ Đã sao lưu: {path}")
            QMessageBox.information(
                self, "Sao lưu",
                f"Sao lưu thành công!\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể sao lưu: {e}")

    def restore_data(self):
        """Khôi phục cơ sở dữ liệu từ bản sao lưu."""
        backups = self.db.get_backup_list()
        if not backups:
            # Cho phép chọn file
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file sao lưu", get_data_dir(),
                "Database Files (*.db)"
            )
            if not file_path:
                return
        else:
            # Hiện danh sách backup
            items = [f"{b['name']} ({b['size'] // 1024} KB)" for b in backups]
            from PySide6.QtWidgets import QInputDialog
            item, ok = QInputDialog.getItem(
                self, "Khôi phục dữ liệu",
                "Chọn bản sao lưu:", items, 0, False
            )
            if not ok:
                return
            idx = items.index(item)
            file_path = backups[idx]['path']

        reply = QMessageBox.warning(
            self, "Xác nhận khôi phục",
            "Khôi phục sẽ thay thế TOÀN BỘ dữ liệu hiện tại.\n"
            "Dữ liệu hiện tại sẽ được sao lưu tự động trước khi khôi phục.\n"
            "Tiếp tục?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            # Auto backup trước khi khôi phục
            self.db.backup_database()
            self.db.restore_database(file_path)
            self.load_data()
            self.status_label.setText("✅ Đã khôi phục dữ liệu thành công")
            QMessageBox.information(self, "Khôi phục",
                                    "Khôi phục dữ liệu thành công!")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể khôi phục: {e}")

    def open_data_folder(self):
        """Mở thư mục dữ liệu trong Explorer."""
        data_dir = get_data_dir()
        os.startfile(data_dir)

    def show_about(self):
        """Hiện thông tin ứng dụng."""
        QMessageBox.about(
            self, "Thông tin",
            "<h3>📦 Theo dõi hành trình đơn hàng</h3>"
            "<p>Phiên bản: 1.0.0</p>"
            "<p>Ứng dụng quản lý và tra cứu hành trình đơn hàng "
            "cho Shopee Express (SPX) và Giao Hàng Nhanh (GHN).</p>"
            f"<p>Dữ liệu lưu tại:<br/><code>{get_data_dir()}</code></p>"
            "<p>Trang tra cứu:<br/>"
            "• SPX: <a href='https://spx.vn/track'>spx.vn/track</a><br/>"
            "• GHN: <a href='https://donhang.ghn.vn'>donhang.ghn.vn</a></p>"
        )

    def closeEvent(self, event):
        """Xử lý khi đóng ứng dụng."""
        if self.tracking_worker and self.tracking_worker.isRunning():
            reply = QMessageBox.question(
                self, "Đang tra cứu",
                "Đang có quá trình tra cứu. Bạn muốn dừng và thoát?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.tracking_worker.cancel()
            self.tracking_worker.wait(5000)

        self.db.close()
        event.accept()
