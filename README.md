# GemLogin Cookie Extractor - Shopee Edition

Công cụ tự động hóa đa luồng hỗ trợ quản lý Profile GemLogin, tự động đăng nhập Shopee và trích xuất Cookie sạch chuẩn MLS.

## Tính năng chính
- Multi-threading: Xử lý đồng thời nhiều profile cùng lúc theo cấu hình Batch Size.
- Tự động Đăng nhập Thông minh:
  - Ưu tiên 1: Đăng nhập bằng Username & Mật khẩu đồng bộ từ Google Sheet (tùy biến Cột User & Cột Profile).
  - Ưu tiên 2: Tự động Fallback sang đăng nhập qua Facebook.
  - Tự động nhận diện Captcha / OTP và dừng chờ người dùng giải.
  - Tự động xử lý màn hình lỗi lưu lượng (Page Unavailable / Traffic Error).
- Trích xuất Cookie tinh gọn: Lọc các cookie cốt lõi (SPC_ST, SPC_U, csrftoken...) chuẩn MLS.
- Tùy biến định dạng xuất: Xuất định dạng Tên|Cookie hoặc Chỉ Cookie.
- Ghi nhớ cấu hình: Tự động lưu và khôi phục cài đặt phiên làm việc trước qua config.json.
- Đẩy code GitHub tự động: Kèm script upload-github.run / upload-github.bat tự động tăng phiên bản (Version Bump).

## Hướng dẫn sử dụng
1. Mở phần mềm bằng cách chạy file run.bat.
2. Chọn thị trường (mặc định PH), nạp Google Sheet hoặc cấu hình số luồng.
3. Tích chọn profile và bấm TỰ ĐỘNG LOGIN & LẤY COOKIE.
