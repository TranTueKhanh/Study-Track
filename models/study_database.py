# ============================================================
# FILE: study_database.py
# Backend quản lý toàn bộ study records của ứng dụng
# Xử lý CRUD, filter, search và dữ liệu statistics
# ============================================================

from datetime import datetime

from data import data_io
from models.entities import StudyRecord


# ============================================================
# STUDY DATABASE
# Service trung tâm cho CRUD + History + Statistics
# ============================================================

class StudyDatabase:

    def __init__(self):

        # Đảm bảo file dữ liệu tồn tại
        data_io.ensure_data_files()

        # Cache toàn bộ records trong RAM
        self.records = list()

        # Load dữ liệu ngay khi khởi tạo service
        self.load_records()

    # ============================================================
    # LOAD / SAVE RECORDS
    # ============================================================

    def load_records(self):

        # Đọc dữ liệu JSON rồi convert thành object StudyRecord
        raw_records = data_io.load_json(data_io.STUDY_RECORDS_PATH, [])

        # self.records luôn được reset từ file để cache không giữ dữ liệu cũ.
        self.records = []

        for record_dict in raw_records:

            try:
                normalized_data = self._build_record_payload(
                    username=record_dict.get("username", ""),
                    record_data=record_dict,
                    record_id=record_dict.get("id"),
                )

                record = StudyRecord(**normalized_data)

                self.records.append(record)

            except (TypeError, ValueError):

                # Bỏ qua record lỗi để tránh crash app
                continue

    def save_records(self):

        # Commit toàn bộ records xuống file JSON
        json_data = []

        for record in self.records:
            json_data.append(record.to_dict())

        data_io.write_json(data_io.STUDY_RECORDS_PATH, json_data)

    # ============================================================
    # GET RECORDS
    # ============================================================

    def get_all_records(self):

        # Trả bản copy để tránh sửa trực tiếp dữ liệu gốc
        return list(self.records)

    def get_records_by_username(self, username: str):

        # Lấy toàn bộ records thuộc về đúng user
        matched_records = []

        normalized_username = self._normalize_text(username).lower()

        for record in self.records:

            if record.username.lower() == normalized_username:
                matched_records.append(record)

        return matched_records

    def count_records_by_username(self, username: str):

        # Đếm nhanh số record của một user, dùng cho thống kê hoặc kiểm tra dữ liệu
        return len(self.get_records_by_username(username))

    def get_record_by_id(self, record_id: int):

        # Tìm record theo ID
        try:
            normalized_id = int(record_id)

        except (TypeError, ValueError):
            return None

        for record in self.records:

            if record.id == normalized_id:
                return record

        return None

    def get_user_record_by_id(self, username: str, record_id: int):

        # Kiểm tra record có thuộc đúng owner không
        record = self.get_record_by_id(record_id)

        if record is None:
            return None

        if record.username.lower() != self._normalize_text(username).lower():
            return None

        return record

    # ============================================================
    # CREATE / UPDATE / DELETE
    # ============================================================

    def get_next_record_id(self):

        # Sinh ID mới cho record tiếp theo
        if not self.records:
            return 1

        return max(record.id for record in self.records) + 1

    def add_record(self, username: str, record_data: dict):

        # Tạo study record mới sau khi validate dữ liệu
        normalized_data = self._build_record_payload(
            username=username,
            record_data=record_data,
            record_id=self.get_next_record_id(),
        )

        new_record = StudyRecord(**normalized_data)

        self.records.append(new_record)

        self.save_records()

        return new_record

    def update_record(self, record_id: int, updated_data: dict, username: str = None):

        # Chỉ cho phép update record thuộc đúng user
        if username is not None:
            matched_record = self.get_user_record_by_id(username, record_id)

        else:
            matched_record = self.get_record_by_id(record_id)

        if matched_record is None:
            raise ValueError("Record not found.")

        merged_data = matched_record.to_dict()

        # Merge dữ liệu cũ với dữ liệu mới từ form
        working_username = username if username is not None else matched_record.username

        working_data = dict(merged_data)

        working_data.update(updated_data)

        normalized_data = self._build_record_payload(
            username=working_username,
            record_data=working_data,
            record_id=matched_record.id,
        )

        validated_record = StudyRecord(**normalized_data)

        # Update từng field để giữ nguyên object reference
        matched_record.username = validated_record.username
        matched_record.date = validated_record.date
        matched_record.subject = validated_record.subject
        matched_record.content = validated_record.content
        matched_record.duration_minutes = validated_record.duration_minutes
        matched_record.effectiveness = validated_record.effectiveness
        matched_record.note = validated_record.note
        matched_record.tag = validated_record.tag
        matched_record.start_time = validated_record.start_time
        matched_record.end_time = validated_record.end_time
        matched_record.mood = validated_record.mood
        matched_record.created_at = validated_record.created_at

        # Update timestamp chỉnh sửa cuối
        matched_record.touch()

        self.save_records()

        return matched_record

    def delete_record(self, record_id: int, username: str = None):

        # Xóa record theo ID
        if username is not None:
            matched_record = self.get_user_record_by_id(username, record_id)

        else:
            matched_record = self.get_record_by_id(record_id)

        if matched_record is None:
            raise ValueError("Record not found.")

        self.records.remove(matched_record)

        self.save_records()

    def delete_records_by_username(self, username: str):

        # Xóa toàn bộ records của một user
        normalized_username = self._normalize_text(username).lower()

        original_count = len(self.records)

        self.records = [
            record
            for record in self.records
            if record.username.lower() != normalized_username
        ]

        removed_count = original_count - len(self.records)

        if removed_count > 0:
            self.save_records()

        return removed_count

    def rename_records_username(self, old_username: str, new_username: str):

        # Đổi owner của toàn bộ records khi user đổi username trong Profile
        normalized_old_username = self._normalize_text(old_username).lower()

        normalized_new_username = self._normalize_text(new_username)

        if not normalized_new_username:
            raise ValueError("Username cannot be empty.")

        renamed_count = 0

        for record in self.records:

            if record.username.lower() != normalized_old_username:
                continue

            record.username = normalized_new_username
            record.touch()
            renamed_count += 1

        if renamed_count > 0:
            self.save_records()

        return renamed_count

    # ============================================================
    # SEARCH / FILTER / SORT
    # ============================================================

    def search_records(self, username: str, keyword: str = "", subject: str = ""):

        # Search records theo keyword + subject
        return self.filter_records(
            username=username,
            keyword=keyword,
            subject=subject,
        )

    def get_subject_list(self, username: str):

        # Lấy danh sách môn học không trùng
        subject_set = set()

        for record in self.get_records_by_username(username):

            if record.subject.strip():
                subject_set.add(record.subject.strip())

        return sorted(subject_set, key=str.lower)

    def filter_records(
        self,
        username: str,
        keyword: str = "",
        subject: str = "",
        from_date: str = "",
        to_date: str = "",
    ):

        # Filter records theo nhiều điều kiện cùng lúc
        records = self.get_records_by_username(username)

        keyword = self._normalize_text(keyword).lower()

        subject = self._normalize_text(subject).lower()

        from_date_obj = self._parse_date_or_none(from_date)

        to_date_obj = self._parse_date_or_none(to_date)

        if from_date and from_date_obj is None:
            raise ValueError("Start date is invalid.")

        if to_date and to_date_obj is None:
            raise ValueError("End date is invalid.")

        if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
            raise ValueError("Start date cannot be later than end date.")

        matched_records = []

        for record in records:

            record_date = self._parse_date_or_none(record.date)

            # Search keyword trong nhiều field
            if keyword:

                search_blob = " ".join(
                    [
                        record.subject.lower(),
                        record.content.lower(),
                        record.note.lower(),
                        record.tag.lower(),
                        record.mood.lower(),
                    ]
                )

                if keyword not in search_blob:
                    continue

            # Filter theo subject
            if subject and record.subject.lower() != subject:
                continue

            # Filter theo khoảng ngày
            if from_date_obj is not None or to_date_obj is not None:

                if record_date is None:
                    continue

                if from_date_obj is not None and record_date < from_date_obj:
                    continue

                if to_date_obj is not None and record_date > to_date_obj:
                    continue

            matched_records.append(record)

        return matched_records

    def sort_records(self, records, sort_by: str = "date", reverse: bool = True):

        # Mapping tiêu chí sort -> hàm xử lý
        sort_key_map = {
            "date": lambda record: self._parse_date_or_min(record.date),
            "subject": lambda record: record.subject.lower(),
            "duration": lambda record: record.duration_minutes,
            "effectiveness": lambda record: record.effectiveness,
            "mood": lambda record: record.mood.lower(),
        }

        normalized_sort_by = self._normalize_text(sort_by).lower()

        sort_key = sort_key_map.get(
            normalized_sort_by,
            sort_key_map["date"]
        )

        return sorted(records, key=sort_key, reverse=reverse)

    # ============================================================
    # DASHBOARD / STATISTICS HELPERS
    # ============================================================

    def get_latest_record(self, username: str):

        # Lấy record mới nhất của user
        user_records = self.get_records_by_username(username)

        if not user_records:
            return None

        return max(
            user_records,
            key=lambda record: (
                self._parse_date_or_min(record.date),
                record.id
            ),
        )

    def get_recent_records(self, username: str, limit: int = 5):

        # Lấy danh sách records gần đây cho dashboard
        sorted_records = self.sort_records(
            self.get_records_by_username(username),
            sort_by="date",
            reverse=True,
        )

        return sorted_records[: max(0, int(limit))]

    def get_subject_minutes(self, username: str):

        # Tính tổng phút học theo từng subject
        subject_minutes = {}

        for record in self.get_records_by_username(username):

            subject_minutes.setdefault(record.subject, 0)

            subject_minutes[record.subject] += record.duration_minutes

        return subject_minutes

    # ============================================================
    # VALIDATION / NORMALIZE
    # Chuẩn hóa và validate dữ liệu trước khi tạo StudyRecord
    # ============================================================

    def _build_record_payload(self, username: str, record_data: dict, record_id):

        normalized_username = self._normalize_text(username)

        normalized_date = self._normalize_date(
            record_data.get("date", "")
        )

        normalized_subject = self._normalize_text(
            record_data.get("subject", "")
        )

        normalized_content = self._normalize_text(
            record_data.get("content", "")
        )

        normalized_note = self._normalize_text(
            record_data.get("note", "")
        )

        normalized_tag = self._normalize_text(
            record_data.get("tag", "")
        )

        normalized_mood = self._normalize_text(
            record_data.get("mood", "")
        )

        normalized_start_time = self._normalize_time(
            record_data.get("start_time", "")
        )

        normalized_end_time = self._normalize_time(
            record_data.get("end_time", "")
        )

        normalized_duration = self._coerce_int(
            record_data.get("duration_minutes", 0),
            field_name="duration_minutes",
        )

        normalized_effectiveness = self._coerce_int(
            record_data.get("effectiveness", 0),
            field_name="effectiveness",
        )

        # Validate logic thời gian học
        self._validate_time_logic(
            start_time=normalized_start_time,
            end_time=normalized_end_time,
            duration_minutes=normalized_duration,
        )

        return {
            "id": int(record_id),
            "username": normalized_username,
            "date": normalized_date,
            "subject": normalized_subject,
            "content": normalized_content,
            "duration_minutes": normalized_duration,
            "effectiveness": normalized_effectiveness,
            "note": normalized_note,
            "tag": normalized_tag,
            "start_time": normalized_start_time,
            "end_time": normalized_end_time,
            "mood": normalized_mood,
            "created_at": record_data.get("created_at", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    # ============================================================
    # HELPER FUNCTIONS
    # ============================================================

    def _normalize_text(self, value):

        # Chuẩn hóa text và bỏ khoảng trắng thừa
        return str(value or "").strip()

    def _coerce_int(self, value, field_name: str):

        # Ép dữ liệu sang int và báo lỗi rõ field
        try:
            return int(value)

        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer.")

    def _normalize_date(self, date_text: str):

        # Convert ngày về YYYY-MM-DD
        parsed_date = self._parse_date_or_none(date_text)

        if parsed_date is None:
            raise ValueError("Study date is invalid.")

        if parsed_date > datetime.today().date():
            raise ValueError("Study date cannot be later than today.")

        return parsed_date.strftime("%Y-%m-%d")

    def _parse_date_or_none(self, date_text: str):

        # Parse nhiều format ngày khác nhau
        date_text = self._normalize_text(date_text)

        if not date_text:
            return None

        date_formats = (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y"
        )

        for fmt in date_formats:

            try:
                return datetime.strptime(date_text, fmt).date()

            except ValueError:
                continue

        return None

    def _normalize_time(self, time_text: str):

        # Convert giờ về format HH:MM
        time_text = self._normalize_text(time_text)

        if not time_text:
            return ""

        time_formats = (
            "%H:%M",
            "%I:%M %p",
            "%I:%M%p"
        )

        for fmt in time_formats:

            try:
                return datetime.strptime(time_text, fmt).strftime("%H:%M")

            except ValueError:
                continue

        raise ValueError("Start time or end time is invalid.")

    def _validate_time_logic(
        self,
        start_time: str,
        end_time: str,
        duration_minutes: int,
    ):

        # Validate logic giữa start/end time
        if (start_time and not end_time) or (end_time and not start_time):
            raise ValueError("Please enter both start time and end time.")

        if not start_time and not end_time:
            return

        start_dt = datetime.strptime(start_time, "%H:%M")

        end_dt = datetime.strptime(end_time, "%H:%M")

        # End time phải sau start time
        if end_dt <= start_dt:
            raise ValueError("End time must be after start time.")

    def _parse_date_or_min(self, date_text: str):

        # Dùng cho sorting nếu ngày lỗi
        parsed_date = self._parse_date_or_none(date_text)

        # Nếu parse lỗi thì dùng ngày nhỏ nhất để sort không bị crash.
        if parsed_date is None:
            return datetime.min.date()

        return parsed_date
