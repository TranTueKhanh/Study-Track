"""
BACKEND LOCAL CHO TÍNH NĂNG TÀI KHOẢN VÀ SETTINGS.

Nếu main.py là nơi người dùng bấm Login/Register/Profile,
thì file này là nơi xử lý dữ liệu thật cho các thao tác đó.

File này phụ trách:
- Đăng ký / đăng nhập / đăng xuất
- Remember me và last user
- Đổi username, password, daily goal
- Đọc, ghi và chuẩn hóa settings của app
"""

from data import data_io
from models.entities import User


# ============================================================
# USER MANAGER
# Service trung tâm quản lý account, user list và settings cục bộ.
# ============================================================
class UserManager:
    """Service trung tâm của tính năng account/settings."""

    def __init__(self):
        # Đảm bảo file dữ liệu tồn tại, sau đó nạp danh sách user vào bộ nhớ.
        data_io.ensure_data_files()

        # self.users là cache user trong RAM, mọi thao tác account sẽ đọc/ghi qua danh sách này.
        self.users = list()
        self.load_users()

    # ============================================================
    # USER STORAGE
    # Đọc/ghi danh sách user giữa file JSON và object User trong app.
    # ============================================================
    def load_users(self):
        """
        Đọc dữ liệu từ users.json và chuyển từng dictionary thành object User.
        Dòng user lỗi sẽ bị bỏ qua để app vẫn chạy được với dữ liệu còn lại.
        """
        raw_users = data_io.load_json(data_io.USERS_PATH, [])
        self.users = []

        for user_dict in raw_users:
            try:
                user = User(
                    username=user_dict["username"],
                    password=user_dict["password"],
                    goal_minutes_per_day=user_dict.get("goal_minutes_per_day", 120),
                    remember_me=user_dict.get("remember_me", False),
                    display_name=user_dict.get("display_name", ""),
                    created_at=user_dict.get("created_at", ""),
                    is_active=user_dict.get("is_active", True),
                )
                self.users.append(user)
            except (KeyError, TypeError, ValueError):
                continue

    def save_users(self):
        """Ghi toàn bộ danh sách user hiện tại xuống users.json."""
        json_data = []
        for user in self.users:
            json_data.append(user.to_dict())

        data_io.write_json(data_io.USERS_PATH, json_data)

    # ============================================================
    # USER LOOKUP
    # Tìm kiếm và kiểm tra trùng username.
    # ============================================================
    def get_user_by_username(self, username: str, include_inactive: bool = True):
        """Tìm user theo username, có thể bỏ qua tài khoản inactive nếu cần."""
        normalized_username = self._normalize_text(username).lower()

        for user in self.users:
            if user.username.lower() != normalized_username:
                continue
            if not include_inactive and not user.is_active:
                return None
            return user
        return None

    def username_exists(self, username: str, include_inactive: bool = True):
        # Dùng khi đăng ký hoặc đổi username để tránh trùng tài khoản.
        return self.get_user_by_username(
            username, include_inactive=include_inactive
        ) is not None

    # ============================================================
    # REGISTER / LOGIN / LOGOUT
    # Xử lý các thao tác tài khoản cơ bản từ màn Login/Register/Profile.
    # ============================================================
    def register_user(
        self,
        username: str,
        password: str,
        confirm_password: str = None,
        display_name: str = "",
    ):
        # Chuẩn hóa dữ liệu trước khi validate và tạo User mới.
        normalized_username = self._normalize_text(username)
        normalized_password = self._normalize_text(password)
        normalized_display_name = self._normalize_text(display_name) or normalized_username

        if confirm_password is not None:
            normalized_confirm_password = self._normalize_text(confirm_password)
            if normalized_password != normalized_confirm_password:
                raise ValueError("Password confirmation does not match.")

        if self.username_exists(normalized_username):
            raise ValueError("Username already exists.")

        self._validate_password_strength(normalized_password)

        new_user = User(
            username=normalized_username,
            password=normalized_password,
            goal_minutes_per_day=120,
            remember_me=False,
            display_name=normalized_display_name,
            is_active=True,
        )

        self.users.append(new_user)
        self.save_users()
        return new_user

    def login_user(self, username: str, password: str, remember_me: bool = False):
        """Xác thực username/password, sau đó lưu remember_me và last_user."""
        normalized_username = self._normalize_text(username)
        normalized_password = self._normalize_text(password)

        user = self.get_user_by_username(normalized_username)
        if user is None or not user.is_active:
            raise ValueError("Incorrect username or password.")

        if normalized_password != user.password:
            raise ValueError("Incorrect username or password.")

        self.set_remembered_user(user.username if remember_me else "")
        self.save_last_user(user.username)
        return user

    def logout_user(self, clear_remembered: bool = False):
        # Xóa last_user; nếu cần thì xóa luôn trạng thái remember_me.
        self.update_settings({"last_user": ""})
        if clear_remembered:
            self.set_remembered_user("")

    # ============================================================
    # PROFILE ACCOUNT UPDATE
    # Đổi password, username, display name, daily goal và xóa user.
    # ============================================================
    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str,
        confirm_password: str = None,
    ):
        user = self.get_user_by_username(username)
        if user is None or not user.is_active:
            raise ValueError("User not found.")

        normalized_old_password = self._normalize_text(old_password)
        normalized_new_password = self._normalize_text(new_password)

        if normalized_old_password != user.password:
            raise ValueError("Current password is incorrect.")

        if confirm_password is not None:
            normalized_confirm = self._normalize_text(confirm_password)
            if normalized_new_password != normalized_confirm:
                raise ValueError("Password confirmation does not match.")

        self._validate_password_strength(normalized_new_password)

        user.password = normalized_new_password
        self.save_users()
        return user

    def update_goal_minutes(self, username: str, goal_minutes_per_day):
        # Tạo User tạm để tận dụng validate trong entity trước khi gán goal mới.
        user = self.get_user_by_username(username)
        if user is None or not user.is_active:
            raise ValueError("User not found.")

        validated_user = User(
            username=user.username,
            password=user.password,
            goal_minutes_per_day=int(goal_minutes_per_day),
            remember_me=user.remember_me,
            display_name=user.display_name,
            created_at=user.created_at,
            is_active=user.is_active,
        )
        user.goal_minutes_per_day = validated_user.goal_minutes_per_day

        self.save_users()
        return user

    def update_display_name(self, username: str, display_name: str):
        # Hiện tại display name được xử lý chung qua update_username theo logic cũ.
        return self.update_username(username, display_name)

    def update_username(self, old_username: str, new_username: str):
        user = self.get_user_by_username(old_username)
        if user is None or not user.is_active:
            raise ValueError("User not found.")

        normalized_new_username = self._normalize_text(new_username)
        existed_user = self.get_user_by_username(normalized_new_username)
        if existed_user is not None and existed_user is not user:
            raise ValueError("New username already exists.")

        validated_user = User(
            username=normalized_new_username,
            password=user.password,
            goal_minutes_per_day=user.goal_minutes_per_day,
            remember_me=user.remember_me,
            display_name=user.display_name,
            created_at=user.created_at,
            is_active=user.is_active,
        )

        old_username_normalized = user.username
        user.username = validated_user.username
        user.display_name = validated_user.display_name

        self.save_users()

        if self.get_last_user() == old_username_normalized:
            self.save_last_user(user.username)

        return user

    def delete_user(self, username: str):
        # Xóa hẳn user khỏi danh sách và dọn last_user/remember_me nếu trùng user đó.
        user = self.get_user_by_username(username)
        if user is None:
            raise ValueError("User not found.")

        self.users.remove(user)
        if self.get_last_user() == user.username:
            self.update_settings({"last_user": ""})
        if user.remember_me:
            self.set_remembered_user("")
        self.save_users()

    # ============================================================
    # REMEMBER ME / LAST USER
    # Phân biệt user đăng nhập gần nhất và user được ghi nhớ tự động.
    # ============================================================
    def save_last_user(self, username: str):
        self.update_settings({"last_user": self._normalize_text(username)})

    def get_last_user(self):
        # Lấy username đăng nhập gần nhất từ settings.
        settings = self.load_settings()
        return settings.get("last_user", "")

    def get_last_logged_in_user(self):

        # Lấy user đăng nhập gần nhất từ settings, bỏ qua tài khoản không còn active.
        last_user = self.get_last_user()
        if not last_user:
            return None
        return self.get_user_by_username(last_user, include_inactive=False)

    def get_remembered_user(self):
        # Tìm user đang bật remember_me thật sự, khác với last_user.
        for user in self.users:
            if user.remember_me and user.is_active:
                return user
        return None

    def set_remembered_user(self, username: str):
        # Chỉ cho phép đúng 1 user được remember_me tại một thời điểm.
        normalized_username = self._normalize_text(username).lower()

        for user in self.users:
            user.remember_me = (
                user.is_active
                and user.username.lower() == normalized_username
                and bool(normalized_username)
            )

        self.save_users()

    # ============================================================
    # SETTINGS
    # Đọc, bổ sung default và chuẩn hóa settings để UI luôn nhận dữ liệu ổn định.
    # ============================================================
    def load_settings(self):
        """
        Đọc settings hiện tại từ file JSON.
        Nếu thiếu key hoặc sai kiểu dữ liệu, hàm sẽ tự sửa về default an toàn.
        """
        default_settings = {
            "last_user": "",
            "default_session_length": 45,
            "theme": "Light",
            "reminder_enabled": True,
            "subject_goals": {},
            "hidden_subjects": [],
        }
        settings = data_io.load_json(data_io.SETTINGS_PATH, default_settings)

        if not isinstance(settings, dict):
            settings = dict(default_settings)

        for key, value in default_settings.items():
            settings.setdefault(key, value)

        try:
            settings["default_session_length"] = int(
                settings.get("default_session_length", 45)
            )
        except (TypeError, ValueError):
            settings["default_session_length"] = 45

        settings["theme"] = self._normalize_text(settings.get("theme", "Light")) or "Light"
        settings["reminder_enabled"] = bool(settings.get("reminder_enabled", True))

        subject_goals = settings.get("subject_goals", {})
        if not isinstance(subject_goals, dict):
            subject_goals = {}
        normalized_subject_goals = {}
        for subject_name, goal_value in subject_goals.items():
            normalized_name = self._normalize_text(subject_name)
            if not normalized_name:
                continue
            try:
                normalized_subject_goals[normalized_name] = max(0, int(goal_value))
            except (TypeError, ValueError):
                normalized_subject_goals[normalized_name] = 120
        settings["subject_goals"] = normalized_subject_goals

        hidden_subjects = settings.get("hidden_subjects", [])
        if not isinstance(hidden_subjects, list):
            hidden_subjects = []
        settings["hidden_subjects"] = [
            normalized_name
            for normalized_name in (
                self._normalize_text(subject_name) for subject_name in hidden_subjects
            )
            if normalized_name
        ]

        return settings

    def update_settings(self, updated_settings: dict):
        """Cập nhật một phần settings mà không ghi đè toàn bộ cấu trúc file."""
        settings = self.load_settings()
        settings.update(updated_settings)
        data_io.write_json(data_io.SETTINGS_PATH, settings)
        return settings

    # ============================================================
    # INTERNAL HELPERS
    # Hàm phụ dùng chung trong class để chuẩn hóa input và validate password.
    # ============================================================
    def _normalize_text(self, value):
        """Chuyển input về chuỗi sạch, tránh lỗi do None hoặc khoảng trắng thừa."""
        return str(value or "").strip()

    def _validate_password_strength(self, password: str):
        """Áp quy tắc mật khẩu tối thiểu cho đăng ký và đổi mật khẩu."""
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")

        has_letter = any(character.isalpha() for character in password)
        has_digit = any(character.isdigit() for character in password)

        if not has_letter or not has_digit:
            raise ValueError("Password must contain at least 1 letter and 1 number.")
