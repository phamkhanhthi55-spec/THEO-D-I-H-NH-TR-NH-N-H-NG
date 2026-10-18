# 🎀 Theo Dõi Hành Trình Đơn Hàng (SPX Express & Giao Hàng Nhanh) 🎀

Ứng dụng Desktop Windows quản lý danh sách đơn hàng và tự động tra cứu hành trình vận chuyển từ **Shopee Express (SPX)** và **Giao Hàng Nhanh (GHN)** với giao diện **Hello Kitty Pastel (Hồng - Trắng - Vàng pastel)** dễ thương, tiện lợi.

---

## 🌟 1. Tính Năng Nổi Bật

- **🎀 Giao diện Pastel dễ thương**: Thiết kế theo phong cách Hello Kitty tone màu Hồng pastel, Trắng và Vàng pastel, chữ màu tương phản dịu mắt, hoàn toàn không gây chói hoặc khó nhìn.
- **🔍 Tra cứu tự động với Playwright**:
  - Tự động nhận diện đơn vị vận chuyển (SPX / GHN) qua mã vận đơn.
  - Sử dụng Playwright headless browser tự động điền mã và lấy thông tin hành trình mới nhất điền vào bảng.
  - Chỉ hiện thông báo lỗi khi tra cứu không thành công, tra cứu thành công sẽ cập nhật trực tiếp vào bảng.
- **📝 Điền & chỉnh sửa trực tiếp trên bảng (In-place Editing)**:
  - Nhấp đúp vào bất kỳ ô nào để sửa nội dung trực tiếp như Excel.
  - Nút **"➕ Thêm dòng"** cho phép thêm dòng mới tinh và gõ trực tiếp ngay trên bảng.
  - Tự động lưu mọi thay đổi vào cơ sở dữ liệu SQLite cục bộ ngay lập tức.
- **📍 Cột thứ 7 – Địa chỉ tùy chọn**:
  - Tích hợp sẵn danh sách lựa chọn nhanh: **Bình Định** và **Quy Nhơn** (người dùng cũng có thể nhập thêm địa chỉ khác).
- **🌸 Thêm cột tùy biến theo nhu cầu**:
  - Nút **"🌸 ➕ Thêm cột"** cho phép tạo thêm không giới hạn các cột mới (ví dụ: *Ghi chú*, *Số điện thoại*, *Phí ship*,...).
  - Dữ liệu các cột tùy biến được lưu trữ vĩnh viễn và đồng bộ khi Xuất file Excel/CSV.
- **📊 Nhập / Xuất dữ liệu Excel & CSV**:
  - Hỗ trợ nhập hàng loạt đơn hàng từ file `.xlsx` và `.csv` (hỗ trợ tiếng Việt UTF-8 BOM).
  - Xuất báo cáo đẹp mắt với định dạng chuẩn, giữ nguyên các cột tùy biến.
- **🛡️ Sao lưu & Khôi phục (Backup & Restore)**:
  - Sao lưu toàn bộ dữ liệu ra file backup bất cứ khi nào, dễ dàng khôi phục khi cần.
  - Dữ liệu hoàn toàn riêng tư, chỉ lưu trên máy tính của bạn (SQLite).

---

## 📋 2. Cấu Trúc Bảng Dữ Liệu Tiêu Chuẩn

Bảng hiển thị mặc định 7 cột tiêu chuẩn:

| Cột | Tên Cột | Mô tả & Quy tắc |
|---|---|---|
| **1** | **STT** | Đánh số tự động (màu vàng pastel), nhấp đúp để xem chi tiết đơn hàng. |
| **2** | **Tên acc đặt** | Tên tài khoản đặt đơn (nhập trực tiếp). |
| **3** | **Tên SP** | Tên sản phẩm gói hàng (nhập trực tiếp). |
| **4** | **Mã vận đơn** | Mã vận đơn SPX hoặc GHN (nhập trực tiếp). |
| **5** | **Hành trình di chuyển** | Cập nhật tự động sau khi bấm "Tra cứu hành trình". |
| **6** | **Số tiền cần thanh toán** | Số tiền người dùng tự nhập (giữ nguyên giá trị). |
| **7** | **Địa chỉ** | Menu lựa chọn: *Bình Định* / *Quy Nhơn* (hoặc nhập thêm). |
| **8+** | **Cột tùy biến** | Các cột do người dùng tự thêm qua nút *"🌸 ➕ Thêm cột"*. |

---

## 🛠️ 3. Cài Đặt & Chạy Từ Mã Nguồn

### Yêu cầu hệ thống:
- Hệ điều hành: Windows 10 / Windows 11
- Python 3.10 trở lên (khuyến nghị Python 3.12 hoặc 3.13)

### Các bước thực hiện:

1. **Clone kho mã nguồn:**
   ```bash
   git clone https://github.com/<tai-khoan>/Theo-doi-hanh-trinh-don-hang.git
   cd Theo-doi-hanh-trinh-don-hang
   ```

2. **Cài đặt các thư viện phụ thuộc:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Cài đặt nhân trình duyệt Playwright:**
   ```bash
   playwright install chromium
   ```

4. **Chạy ứng dụng:**
   ```bash
   python run.py
   ```

---

## 📦 4. Đóng Gói Thành File `.exe` Chạy Độc Lập

Dự án đã cấu hình sẵn file `Theo-doi-hanh-trinh-don-hang.spec` để đóng gói bằng PyInstaller:

```bash
pyinstaller Theo-doi-hanh-trinh-don-hang.spec --noconfirm
```

Sau khi hoàn tất, file thực thi sẽ nằm tại:
`dist/Theo-doi-hanh-trinh-don-hang/Theo-doi-hanh-trinh-don-hang.exe`

---

## 📁 5. Cấu Trúc Thư Mục Dự Án

```text
Theo-doi-hanh-trinh-don-hang/
│
├── src/                               # Toàn bộ mã nguồn chương trình
│   ├── __init__.py
│   ├── app.py                         # Khởi tạo QApplication & cấu hình High DPI
│   ├── main_window.py                 # Giao diện chính, bảng dữ liệu, chỉnh sửa trực tiếp
│   ├── database.py                    # Quản lý cơ sở dữ liệu SQLite & migrations
│   ├── carrier.py                     # Nhận diện đơn vị vận chuyển (SPX / GHN)
│   ├── tracking.py                    # Worker tra cứu tự động qua Playwright
│   └── data_io.py                     # Đọc & ghi file Excel / CSV
│
├── tests/                             # Bộ kiểm thử tự động (Unit Tests)
│   ├── test_app.py                    # Kiểm thử Database, Carrier, Cột
│   ├── test_data_io.py                # Kiểm thử Nhập/Xuất Excel & CSV
│   └── test_gui.py                    # Kiểm thử giao diện Qt headless
│
├── resources/                         # Hình ảnh & icon ứng dụng
│   ├── hello_kitty.png                # Sticker trang trí Hello Kitty
│   ├── icon.png                       # Icon chuẩn PNG
│   └── icon.ico                       # Icon ứng dụng Windows
│
├── data/                              # File dữ liệu mẫu
│   ├── mau_don_hang.xlsx              # Mẫu Excel
│   └── mau_don_hang.csv               # Mẫu CSV
│
├── run.py                             # Script khởi chạy ứng dụng
├── requirements.txt                   # Danh sách thư viện Python
├── Theo-doi-hanh-trinh-don-hang.spec  # Cấu hình đóng gói PyInstaller
├── .gitignore                         # Loại trừ file rác & dữ liệu cá nhân
├── LICENSE                            # Giấy phép mã nguồn mở MIT
└── README.md                          # Hướng dẫn sử dụng chi tiết
```

---

## 🔒 6. Chính Sách Bảo Mật Dữ Liệu

- Ứng dụng **không** gửi dữ liệu đơn hàng, thông tin tài khoản hay số tiền lên bất kỳ máy chủ nào.
- File cơ sở dữ liệu SQLite được lưu cục bộ an toàn tại thư mục `%APPDATA%\TheoDoiHanhTrinhDonHang\orders.db` của người dùng.
- File `.gitignore` đã được cấu hình chặt chẽ để loại trừ mọi file cơ sở dữ liệu cá nhân (`*.db`, `*.sqlite`) và các file Excel/CSV riêng tư, đảm bảo an toàn tuyệt đối khi đồng bộ lên GitHub.

---

## 📄 7. Giấy Phép (License)

Dự án được phân phối dưới giấy phép [MIT License](LICENSE).
