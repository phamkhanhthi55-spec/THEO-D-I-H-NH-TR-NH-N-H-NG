"""
Điểm khởi chạy ứng dụng Theo dõi hành trình đơn hàng.
"""

import sys
import os

# Thêm thư mục gốc vào sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def main():
    """Khởi chạy ứng dụng."""
    # Cấu hình đường dẫn Playwright Browser
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    ms_playwright = os.path.join(local_app_data, "ms-playwright") if local_app_data else ""
    if ms_playwright and os.path.exists(ms_playwright):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Theo dõi hành trình đơn hàng")
    app.setOrganizationName("OrderTracker")

    # Áp dụng giao diện Fusion và bảng màu Pastel để không bị ảnh hưởng bởi Windows Dark Mode
    app.setStyle("Fusion")
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#FFF5F8"))
    palette.setColor(QPalette.WindowText, QColor("#4A3B43"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#FFF8FA"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFF9D2"))
    palette.setColor(QPalette.ToolTipText, QColor("#795548"))
    palette.setColor(QPalette.Text, QColor("#4A3B43"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#C2185B"))
    palette.setColor(QPalette.BrightText, QColor("#D81B60"))
    palette.setColor(QPalette.Link, QColor("#E91E63"))
    palette.setColor(QPalette.Highlight, QColor("#FFD6E2"))
    palette.setColor(QPalette.HighlightedText, QColor("#880E4F"))
    app.setPalette(palette)

    # Set icon
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'resources', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Set font
    from PySide6.QtGui import QFont
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Tạo cửa sổ chính
    from src.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
