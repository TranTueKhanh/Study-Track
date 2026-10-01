# Study Track

Ứng dụng quản lý và theo dõi học tập được xây dựng bằng Python + PyQt6.

Study Track giúp người dùng:
- ghi lại lịch sử học tập
- theo dõi thời gian học
- xem thống kê và biểu đồ học tập
- quản lý mục tiêu học mỗi ngày
- theo dõi streak và KPI học tập

---

# Công nghệ sử dụng

- Python 3
- PyQt6
- JSON Local Storage
- Dataclass
- QtCharts

---

# Kiến trúc dự án

```text
project/
│
├── main.py
│   └── Entry point + UI controller
│
├── models/
│   ├── __init__.py
│   ├── entities.py
│   ├── insight_service.py
│   ├── study_database.py
│   └── user_manager.py
│
├── data/
│   ├── data_io.py
│   ├── users.json
│   ├── study_records.json
│   └── settings.json
│
├── ui/
│   ├── login.ui
│   ├── register.ui
│   ├── dashboard.ui
│   ├── crud.ui
│   ├── history.ui
│   ├── statistics.ui
│   ├── profile.ui
│   └── session.ui
│
└── assets/
```

---

# Tổng quan các thành phần

## 1. `main.py`

File điều phối trung tâm của ứng dụng.

Chức năng:
- load giao diện `.ui`
- điều hướng giữa các màn hình
- xử lý signal/button
- quản lý session timer
- đồng bộ UI với backend
- hiển thị popup/thông báo

Các màn hình chính:
- Login
- Register
- Dashboard
- Study Session
- CRUD Record
- History
- Statistics
- Profile

---

## 2. `models/entities.py`

Định nghĩa entity chuẩn cho toàn bộ dữ liệu của app.

### `User`
Đại diện cho tài khoản người dùng.

### `StudyRecord`
Đại diện cho một phiên học.

---

## 3. `models/user_manager.py`

Service xử lý toàn bộ tính năng account/settings.

Chức năng:
- đăng ký
- đăng nhập
- remember me
- đổi password
- đổi username
- lưu settings
- quản lý goal học tập

---

## 4. `models/study_database.py`

Backend CRUD cho study records.

Chức năng:
- add/edit/delete records
- search/filter/sort
- load/save JSON
- lấy dữ liệu dashboard
- lấy dữ liệu statistics

---

## 5. `models/insight_service.py`

Tầng phân tích dữ liệu học tập.

Chức năng:
- tính KPI dashboard
- tính streak
- tính goal progress
- tạo insight text
- tạo dữ liệu biểu đồ
- thống kê theo ngày/môn học

---

# Các tính năng chính

## Dashboard
- tổng phút học hôm nay
- tổng phút học tuần này
- streak học tập
- top subject
- recent activity
- suggestion text

## Study Session
- timer học tập
- start/pause/reset
- auto sync duration
- save nhanh record

## CRUD Record
- thêm record mới
- chỉnh sửa record
- validate dữ liệu
- validate thời gian học

## History
- search keyword
- filter theo subject
- filter theo ngày
- sort records

## Statistics
- biểu đồ môn học
- biểu đồ xu hướng học
- thống kê thời gian học
- thống kê streak

## Profile
- đổi password
- đổi username
- đổi daily goal
- remember me
- settings app

---

# Validation & Data Safety

Ứng dụng có validate cho:
- username/password
- study date
- start/end time
- effectiveness
- duration
- duplicate username

Dữ liệu lỗi sẽ:
- không làm crash app
- được bỏ qua an toàn
- hiện popup lỗi rõ ràng

---

# Design Pattern

## UI Layer
- `main.py`
- `.ui`

## Service Layer
- `UserManager`
- `StudyDatabase`
- `InsightService`

## Entity Layer
- `User`
- `StudyRecord`

## Storage Layer
- `data_io.py`
- JSON files

---

# Cách chạy project

## Cài dependencies

```bash
pip install PyQt6
```

## Chạy ứng dụng

```bash
python main.py
```