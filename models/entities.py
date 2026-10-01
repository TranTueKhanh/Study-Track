# ============================================================
# FILE: entities.py
# Entity chuẩn cho toàn bộ dữ liệu chính của ứng dụng.
# File này chỉ định nghĩa cấu trúc dữ liệu, không xử lý UI.
# ============================================================

from dataclasses import asdict, dataclass, field
from datetime import datetime


# ============================================================
# INTERNAL HELPER
# Hàm phụ chuẩn hóa timestamp về format ISO datetime.
# ============================================================

def _normalize_iso_datetime(value: str):

    # Chuẩn hóa timestamp để tránh sai format khi lưu JSON
    value = str(value or "").strip()

    if not value:
        return datetime.now().isoformat(timespec="seconds")

    try:
        return datetime.fromisoformat(value).isoformat(timespec="seconds")

    except ValueError as error:
        raise ValueError(
            "Timestamp fields must be valid ISO datetime."
        ) from error


# ============================================================
# USER ENTITY
# Entity đại diện cho tài khoản người dùng trong app.
# ============================================================

@dataclass
class User:

    # ============================================================
    # USER FIELDS
    # Các field chuẩn của một user hợp lệ trong app.
    # ============================================================

    username: str

    password: str

    goal_minutes_per_day: int = 120

    remember_me: bool = False

    display_name: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    is_active: bool = True

    # ============================================================
    # POST INIT
    # Validate và normalize dữ liệu ngay khi tạo object.
    # ============================================================

    def __post_init__(self):

        # Làm sạch text input
        self.username = self.username.strip()

        self.password = self.password.strip()

        self.display_name = self.username

        # Chuẩn hóa kiểu dữ liệu
        self.goal_minutes_per_day = int(self.goal_minutes_per_day)

        self.remember_me = bool(self.remember_me)

        self.is_active = bool(self.is_active)

        self.created_at = _normalize_iso_datetime(self.created_at)

        # Validate dữ liệu user
        if not self.username:
            raise ValueError("Username cannot be empty.")

        if not self.password:
            raise ValueError("Password cannot be empty.")

        if not self.display_name:
            raise ValueError("Display name cannot be empty.")

        if self.goal_minutes_per_day <= 0:
            raise ValueError(
                "Goal minutes per day must be greater than 0."
            )

    # ============================================================
    # SERIALIZATION
    # Convert object -> dict để lưu JSON.
    # ============================================================

    def to_dict(self):

        # Convert toàn bộ object thành dictionary
        payload = asdict(self)

        payload["display_name"] = self.username

        return payload

    def public_dict(self):

        # Trả thông tin user nhưng ẩn password
        payload = self.to_dict()

        payload.pop("password", None)

        return payload


# ============================================================
# STUDY RECORD ENTITY
# Entity đại diện cho một study record trong app.
# ============================================================

@dataclass
class StudyRecord:

    # ============================================================
    # RECORD FIELDS
    # Các field chuẩn của một study record hợp lệ.
    # ============================================================

    id: int

    username: str

    date: str

    subject: str

    content: str

    duration_minutes: int

    effectiveness: int

    note: str = ""

    tag: str = ""

    start_time: str = ""

    end_time: str = ""

    mood: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    # ============================================================
    # POST INIT
    # Normalize + validate dữ liệu record sau khi khởi tạo.
    # ============================================================

    def __post_init__(self):

        # Làm sạch text từ form/UI
        self.username = self.username.strip()

        self.date = self.date.strip()

        self.subject = self.subject.strip()

        self.content = self.content.strip()

        self.note = self.note.strip()

        self.tag = self.tag.strip()

        self.start_time = self.start_time.strip()

        self.end_time = self.end_time.strip()

        self.mood = self.mood.strip()

        # Chuẩn hóa timestamp
        self.created_at = _normalize_iso_datetime(self.created_at)

        self.updated_at = _normalize_iso_datetime(self.updated_at)

        # Chuẩn hóa kiểu dữ liệu
        self.id = int(self.id)

        self.duration_minutes = int(self.duration_minutes)

        self.effectiveness = int(self.effectiveness)

        # Validate dữ liệu record
        if not self.username:
            raise ValueError("Username cannot be empty.")

        if not self.date:
            raise ValueError("Date cannot be empty.")

        if not self.subject:
            raise ValueError("Subject cannot be empty.")

        if not self.content:
            raise ValueError("Content cannot be empty.")

        if self.id <= 0:
            raise ValueError("Record id must be greater than 0.")

        if self.duration_minutes < 0:
            raise ValueError("Duration must be 0 or greater.")

        if not 0 <= self.effectiveness <= 5:
            raise ValueError(
                "Effectiveness must be between 0 and 5."
            )

    # ============================================================
    # SERIALIZATION
    # Convert record object -> dictionary để lưu JSON.
    # ============================================================

    def to_dict(self):

        return asdict(self)

    # ============================================================
    # RECORD UPDATE HELPER
    # Update timestamp mỗi lần chỉnh sửa record.
    # ============================================================

    def touch(self):

        # Đánh dấu thời điểm record được update cuối cùng
        self.updated_at = datetime.now().isoformat(timespec="seconds")