# Girl X Battle Reborn

Nghiên cứu khả năng khôi phục trải nghiệm chơi **offline** cho Girl X Battle, dựa trên APK gốc và chỉ phục vụ mục đích lưu trữ/cá nhân.

## Mục tiêu

- Phân tích APK để nhận diện engine, endpoint và giao thức mạng.
- Lập bản đồ các dịch vụ backend mà game cần để khởi động và vào trận.
- Đánh giá phần nào có thể mô phỏng cục bộ trên thiết bị hoặc qua máy chủ LAN.
- Lưu tài liệu giao thức và mã máy chủ mới, độc lập với tài sản/phần mềm không được cấp phép.

## APK nguồn

Không commit APK vào Git, vì kích thước lớn. Hãy đính kèm bản APK vào một GitHub Release của repository này. Ghi rõ trong release:

- tên tệp APK;
- phiên bản game/build number (nếu biết);
- SHA-256 của tệp.

Sau khi release được tạo, APK sẽ được tải về để phân tích cục bộ và không được đưa trở lại Git.

## Cấu trúc dự kiến

```text
docs/       Ghi chép về kiến trúc, endpoint và định dạng gói tin
tools/      Script tái lập được dùng để trích xuất/phân tích APK
server/     Mã nguồn server offline (chỉ tạo sau khi xác định giao thức)
```

## Lưu ý

Chỉ sử dụng APK mà bạn có quyền lưu trữ và phân tích. Không đưa khóa ký, token, dữ liệu tài khoản hay nội dung bản quyền không cần thiết vào repository.
