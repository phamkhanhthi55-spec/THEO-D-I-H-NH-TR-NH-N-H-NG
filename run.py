"""
Khởi chạy ứng dụng Theo dõi hành trình đơn hàng.
File này nằm ở thư mục gốc dự án để dễ chạy.
"""

import sys
import os

# Thêm thư mục hiện tại vào path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import main

if __name__ == '__main__':
    main()
