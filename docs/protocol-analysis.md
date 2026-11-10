# Đánh giá giao thức và khả năng chạy offline

Phân tích tĩnh APK `girls-x-battle-1-631-0.apk` từ release `base-apk`.

- SHA-256: `11e80f259db780feb916a8fdc7bab802c2740087a31652e2977c7de6f755595f`
- Dung lượng: 153,501,878 byte
- Không chạy APK, không gửi request tới máy chủ game cũ trong quá trình phân tích.

## Kết luận

**Khả thi để làm bản chơi offline**, trước hết với một tài khoản cục bộ và các chế độ đơn. Đây không phải trường hợp phải viết lại cả game: APK chứa Cocos2d-x, LuaJIT bytecode, mã chiến đấu phía client (`assets/src_64/lib/battle/`), UI, bảng nhân vật/vật phẩm/campaign và phần lớn tài nguyên.

Phần cần tái tạo là backend lưu trạng thái và trả lời API. Làm lại toàn bộ game online (chat, guild, đấu hạng, bảng xếp hạng và mọi sự kiện theo mùa) là dự án lớn; không cần làm các phần đó để có một bản chơi cá nhân.

## Kiến trúc phát hiện được

```text
APK Cocos2d-x / LuaJIT
        |
        | POST payload=<JSON URL-encoded>
        v
Center bootstrap (mid 20480) --> trả về URL API
        |
        | POST payload=<JSON URL-encoded>
        v
API chính (dispatcher theo mid) --> JSON response
        |
        +--> TCP riêng cho chat (có thể bỏ qua ở MVP offline)
```

Mã liên quan:

- `assets/src_64/UpdateScene_64.lua`: bootstrap và cập nhật;
- `assets/src_64/app/common/network/Backend.lua`: HTTP API, token, chat TCP;
- `assets/src_64/app/common/network/mid.lua`: bảng mã lệnh;
- `assets/src_64/app/scenes/LoadingScene.lua`: login;
- `assets/src_64/app/windows/LoginWindow.lua`: chọn tài khoản/region.

## Bootstrap và API HTTP

`UpdateScene_64.lua` gửi HTTP POST với trường `payload` là JSON thô:

```json
{
  "mid": 20480,
  "area": "tw",
  "type": "<mode trong infos.xml>",
  "app_v": "<version>",
  "platform": "<Android platform id>"
}
```

Client chờ một JSON có tối thiểu trường `url`; sau đó gán trường này thành `xyd.serverUrl`. Các trường tùy chọn khác là `server_id`, `back_domain`, `res_download_url`.

Các địa chỉ bootstrap/API gốc được phát hiện trong bản APK là endpoint lịch sử và không nên sử dụng lại. Thay vào đó bản đã vá phải trỏ bootstrap về companion server cục bộ (ví dụ `http://127.0.0.1:<port>/center/v1`) hoặc bỏ qua bootstrap để gán trực tiếp API URL.

Sau bootstrap, request thông thường tới API chính có dạng:

```http
POST /api/v1
Content-Type: application/x-www-form-urlencoded

payload=%7B%22mid%22%3A18%2C...%7D
```

JSON request luôn được bổ sung các trường `mid`, `token`, `region`, `v_`, `app_v`, `platform`. Response thành công là JSON trực tiếp, HTTP 200. Một nhóm nhỏ request ghi nhận kết quả trận dùng JSON nén zlib trong form data; nhóm đó chưa cần cho milestone login/UI.

## Đăng nhập và lệnh nền tảng

Các lệnh đã xác định từ `mid.lua`:

| mid | Lệnh | Vai trò offline |
| ---: | --- | --- |
| 18 | `LOAD_USER_REGIONS` | Trả danh sách một region cục bộ và, nếu cần, danh sách nhân vật lưu.
| 1 | `RETRIEVE_TOKEN` | Nhận `sid`, `login_token`, `region`; trả `token`, `region`, `is_new` và dữ liệu login tối thiểu.
| 7 | `LOAD_ANNOUNCE` | Có thể trả nội dung rỗng.
| 17 | `LOAD_PLAYER_INFO` | Thông tin tài khoản/nhân vật.
| 20, 21 | `LOAD_SCROLLS`, `LOAD_ESSENCES` | Kho cuộn và essence.
| 49, 65, 67 | `LOAD_HEROS`, `LOAD_COLLECTED_HEROS`, `LOAD_HERO_PIECES` | Dữ liệu nhân vật.
| 81 | `LOAD_BACKPACK` | Túi đồ.
| 112, 115 | `LOAD_WORLD_MAP`, `LOAD_TRIAL_INFOS` | Campaign/thử thách.
| 144, 160, 208, 211 | Building, mission, đội hình, mượn hero | Cần cho UI chính tùy tiến độ.
| 229 | `ACTIVITIES` | Có thể trả danh sách rỗng ở MVP.

Sau login, client đã có mã để tải và hiển thị game, nhưng sẽ gọi nhiều `mid` theo hành động người chơi. Một server offline nên dùng dispatcher theo `mid`, trả lỗi có kiểm soát cho tính năng chưa có thay vì cố mô phỏng mọi event ngay từ đầu.

## TCP chat

Chat là nhánh riêng. API `LOAD_CHAT_ROOM_INFO` (192) trả `host`, `port`, `room_id`; client sau đó mở TCP và gửi `TCP_LOGIN` (32771), heartbeat (32797) và tin nhắn (32782).

Phần native có `TCPSocket` và sproto, nên định dạng khung TCP cần phân tích riêng nếu muốn chat. Với bản một người offline, nên vô hiệu hóa/hide chat hoặc để backend không cấp phòng chat. Chat không phải blocker cho login, main screen, campaign và chiến đấu đơn.

## Điểm cần vá trên Android

APK hiện lấy API URL từ bootstrap. Vì vậy chỉ dựng server là chưa đủ: client phải được trỏ về server local.

1. Giải mã/chỉnh `UpdateScene_64.lua` để thay URL bootstrap hoặc đặt thẳng `xyd.serverUrl`.
2. Biên dịch lại LuaJIT bytecode, đóng gói lại APK và ký bằng khóa mới.
3. Cài bản APK đã ký mới (thường cần gỡ bản gốc trước do khác chữ ký).
4. Chạy companion server trên chính điện thoại, ví dụ trong Termux, lắng nghe `127.0.0.1`; hoặc dùng một máy trong LAN trong giai đoạn phát triển.

Không thể chỉ sửa DNS một cách đáng tin cậy trên Android không root, vì URL bootstrap được hard-code trong LuaJIT bytecode. Cách vá client là con đường bền vững.

## Lộ trình đề xuất

1. Dựng API logger/mock cục bộ: parse `payload`, ghi request đã giải mã và trả JSON cơ bản.
2. Vá bootstrap để APK kết nối `127.0.0.1` hoặc một host LAN; ký lại và chạy thử trên máy Android.
3. Hoàn thiện 3 response đầu: 20480, 18, 1; xác nhận vào login/main scene.
4. Thêm SQLite cho player, heroes, inventory, campaign và formation; ưu tiên các `mid` trong bảng trên.
5. Đối chiếu request/response khi mở từng màn hình để bổ sung handler đúng lúc.
6. Chỉ phân tích TCP nếu quyết định giữ chat; không đưa vào MVP.

## Rủi ro kỹ thuật

- Luajit bytecode có thể dịch ngược không hoàn hảo; dùng bytecode và hành vi client làm nguồn kiểm chứng.
- Một số response chứa cấu trúc lồng nhau lớn. Schema nên được lấy từ các model Lua và log request theo từng màn hình.
- Server phải giữ state hợp lệ, không chỉ trả `{}`; nếu không UI/model sẽ lỗi khi đọc các trường bắt buộc.
- Các tính năng online/commerce nên tắt trong bản offline; không nên mô phỏng thanh toán hoặc dịch vụ bên thứ ba.
