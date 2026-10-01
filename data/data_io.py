import json
from pathlib import Path


# Đường dẫn gốc của project.
BASE_DIR = Path(__file__).resolve().parent.parent

# Thư mục chứa dữ liệu JSON.
DATA_DIR = BASE_DIR / "data"

# File lưu tài khoản người dùng.
USERS_PATH = DATA_DIR / "users.json"

# File lưu study records.
STUDY_RECORDS_PATH = DATA_DIR / "study_records.json"

# File lưu settings ứng dụng.
SETTINGS_PATH = DATA_DIR / "settings.json"


# Tạo thư mục data nếu chưa tồn tại.
def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# Tạo các file JSON mặc định nếu chưa có.
def ensure_data_files():
    ensure_data_dir()

    defaults = {
        USERS_PATH: [],
        STUDY_RECORDS_PATH: [],
        SETTINGS_PATH: {"last_user": ""},
    }

    for path, default_value in defaults.items():
        if not path.exists():
            write_json(path, default_value)


# Đọc dữ liệu JSON an toàn từ file.
def load_json(path: Path, default_value):
    ensure_data_files()
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    # Nếu file lỗi thì trả dữ liệu mặc định.
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default_value


# Ghi dữ liệu JSON xuống file.
def write_json(path: Path, payload):
    ensure_data_dir()

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


# Thêm một item mới vào danh sách JSON.
def append_json_item(path: Path, item, default_value=None):

    # Nếu caller không truyền default thì mặc định file này chứa danh sách.
    default_value = default_value if default_value is not None else []

    # Load danh sách hiện tại, thêm item mới rồi ghi ngược lại file.
    data = load_json(path, default_value)

    data.append(item)

    write_json(path, data)
