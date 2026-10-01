# Kế hoạch 4 round: Smart Study Tracker

## Tóm tắt

Xây dựng ứng dụng desktop `PyQt6 + .ui + JSON + OOP` bám đúng lesson samples: model class, CRUD, đọc/ghi JSON, event handling, nhiều màn hình UI. Phạm vi bản cuối khóa là `single-user local`, có `login/register` bằng file JSON, phần thống kê ưu tiên `KPI + insight text`, không phụ thuộc thư viện chart ngoài khung PTI.

Mục tiêu cuối cùng sau round 4: app chạy được end-to-end từ đăng ký/đăng nhập đến thêm-sửa-xóa bản ghi học, xem dashboard, tìm kiếm/sắp xếp lịch sử, xem thống kê cơ bản và gợi ý học tập từ dữ liệu thật.

## Thiết kế triển khai

### Kiến trúc và interface chính

- `StudyRecord`
  - Trường bắt buộc: `id`, `date`, `subject`, `content`, `duration_minutes`, `effectiveness`
  - Trường dùng trong v1 nếu đủ thời gian: `note`, `tag`
- `User`
  - Trường: `username`, `password`, `goal_minutes_per_day`
- File dữ liệu:
  - `users.json`: danh sách user local
  - `study_records.json`: danh sách record, mỗi record gắn `username`
  - `settings.json`: cấu hình tối thiểu như `last_user` hoặc theme nếu cần
- Lớp xử lý:
  - `StudyDatabase` quản lý load/save/filter/sort/search records
  - `UserManager` xử lý register/login/check duplicate username
  - `InsightService` tính KPI, streak, top subject, goal progress, text suggestion
- UI flow:
  - `Login` -> `Register` -> `Dashboard`
  - Từ `Dashboard` điều hướng sang `Add/Edit Record`, `History`, `Statistics`
- Không làm ở v1:
  - Database thật, cloud, dark mode thật, export file nâng cao, chart library ngoài môn

### Round 1: Hoàn thiện khung giao diện toàn app

- Chốt cấu trúc thư mục theo lesson samples: `data/`, `models/`, `ui/`, `main.py`
- Dựng hoặc rà soát đầy đủ các file `.ui` cho toàn bộ app:
  - `login.ui`
  - `register.ui`
  - `dashboard.ui`
  - `studysession.ui` hoặc form `Add/Edit Record`
  - `history.ui`
  - `statistics.ui` nếu có
- Chốt flow giao diện trước khi code:
  - `Login` -> `Register` -> `Dashboard`
  - Từ `Dashboard` điều hướng sang `Add/Edit Record`, `History`, `Statistics`
- Chuẩn hóa tên widget, `objectName`, label, button, placeholder cho từng màn
- Kết quả round:
  - Có đủ bộ khung UI cho toàn bộ app
  - Luồng người dùng rõ ràng trên giao diện
  - Chưa làm logic Python, ưu tiên chốt phần nhìn trước

### Round 2: Polish toàn bộ UI/UX trước khi nối code

- Hoàn thiện bố cục và trải nghiệm cho tất cả màn `.ui`
- Bổ sung các trạng thái giao diện cần dùng:
  - Empty state khi chưa có record
  - Khu vực KPI cards trên dashboard
  - Khu vực recent records, insight text, search/filter/sort
  - Form add/edit record đủ field: `date`, `subject`, `content`, `duration_minutes`, `effectiveness`
- Làm màn `Statistics` mức PTI:
  - KPI cards
  - Phân bổ theo môn bằng text/tỷ lệ hoặc progress bar
  - Tổng hợp 7 ngày gần nhất bằng danh sách/tóm tắt số liệu
- Rà soát thống nhất spacing, alignment, size, text hiển thị giữa các màn
- Kết quả round:
  - Toàn bộ UI hoàn chỉnh trước khi viết logic
  - Có thể demo prototype đầy đủ màn hình
  - Round sau chỉ tập trung nối Python và dữ liệu

### Round 3: Nối Python cho auth, điều hướng và CRUD

- Tạo model `User`, `StudyRecord`, database class đọc/ghi JSON
- Chuẩn hóa schema cho `users.json` và `study_records.json`
- Tạo `main.py` hoặc `app_controller.py` để chuyển màn hình
- Nối `login.ui` và `register.ui` vào code PyQt6:
  - Đăng ký user mới
  - Đăng nhập user đã có
  - Validation cơ bản: rỗng field, confirm password sai, username trùng
- Kết nối form `Add/Edit Record` để chạy CRUD thật:
  - Thêm record
  - Sửa record
  - Xóa record
  - Lưu ngay xuống `study_records.json`
- Làm màn `History` hoặc khu vực danh sách record:
  - Hiển thị record theo user đang đăng nhập
  - Chọn record để edit/delete
- Validation dữ liệu:
  - Ngày hợp lệ
  - Môn học không rỗng
  - Thời lượng là số dương
  - Effectiveness trong khoảng 1-5
- Kết quả round:
  - User có thể đăng ký/đăng nhập và quản lý bản ghi thật từ giao diện
  - Dữ liệu đóng app mở lại vẫn còn

### Round 4: Nối dashboard/statistics, insight và polish demo

- Nối `dashboard.ui` với dữ liệu thật thay vì text tĩnh
- Tính và đổ dữ liệu vào dashboard:
  - Tổng phút học hôm nay
  - Tổng phút học tuần này
  - Streak ngày học liên tiếp
  - Môn học nhiều thời gian nhất
  - Recent records
- Làm search/sort/filter trong `History`:
  - Tìm theo subject hoặc content
  - Sắp xếp theo ngày, subject, effectiveness, duration
- Viết `InsightService` sinh gợi ý text từ data:
  - Môn học bị lệch
  - Chưa đạt goal ngày
  - Bỏ trống môn nhiều ngày
  - Môn chiếm nhiều thời gian nhất
- Rà soát toàn bộ luồng điều hướng giữa các màn
- Cải thiện UX:
  - Thông báo thành công/lỗi bằng `QMessageBox`
  - Nút quick add / start session nếu còn thời gian
- Nếu còn dư thời gian:
  - Timer học đơn giản start/pause/end và khi end tạo record nháp
- Chuẩn bị demo:
  - Seed data mẫu
  - Kịch bản demo 3-5 phút
  - Danh sách điểm nhấn kỹ thuật để trình bày
- Kết quả round:
  - Bản nộp ổn định, demo mượt, đủ CRUD + JSON + GUI + search/sort + insight
  - Đúng trình tự làm: xong UI trước rồi mới code Python

## Test plan

- Register:
  - Tạo tài khoản mới hợp lệ
  - Username trùng bị chặn
  - Password confirm sai bị chặn
- Login:
  - Đăng nhập đúng thông tin
  - Sai user hoặc password báo lỗi
- CRUD:
  - Thêm record mới
  - Sửa record cập nhật đúng JSON
  - Xóa record biến mất khỏi UI và file
- History:
  - Search theo subject/content trả đúng danh sách
  - Sort theo ngày và effectiveness đúng thứ tự
- Dashboard/Statistics:
  - KPI đổi đúng khi thêm/xóa record
  - Top subject, today/week totals, streak đúng với dữ liệu mẫu
  - Insight text đổi theo tình huống dữ liệu
- Persistence:
  - Tắt app mở lại vẫn giữ user và records

## Giả định đã khóa

- Công nghệ giới hạn trong phạm vi lesson samples: `Python`, `PyQt6`, `.ui`, `JSON`, `OOP`, xử lý dữ liệu bằng code tự viết.
- Bản cuối khóa là `single-user local` theo nghĩa không có server hay online auth; vẫn có nhiều tài khoản trong `users.json` nhưng app vận hành local.
- Phần thống kê ưu tiên số liệu + insight text; nếu có chart thì chỉ là bổ sung sau khi core features đã xong.
- `Timer`, `Profile`, `Settings`, `Dark mode`, `Export JSON` không phải hạng mục bắt buộc để pass demo; chỉ làm khi 4 round core đã ổn định.
