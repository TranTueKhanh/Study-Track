# ============================================================
# FILE: insight_service.py
# Tầng phân tích local cho Dashboard, History và Statistics.
# File này đọc study records rồi tính KPI, insight và dữ liệu biểu đồ.
# ============================================================

from collections import defaultdict
from datetime import datetime, timedelta


# ============================================================
# INSIGHT SERVICE
# Service chứa các hàm thống kê, KPI và gợi ý học tập.
# ============================================================

class InsightService:

    # ============================================================
    # DASHBOARD KPI
    # Các hàm tính chỉ số chính hiển thị trên Dashboard.
    # ============================================================

    @staticmethod
    def get_total_minutes_today(records, today=None):

        # Tính tổng số phút học trong ngày hôm nay
        # `today` có thể truyền vào để test, nếu không sẽ dùng ngày hiện tại
        today_text = InsightService._normalize_today_text(today)

        return sum(
            record.duration_minutes
            for record in records
            if record.date == today_text
        )

    @staticmethod
    def get_total_minutes_this_week(records, today=None):

        # Tính tổng phút học trong tuần hiện tại
        # Tuần được tính từ Thứ 2 đến Chủ nhật
        today_date = InsightService._normalize_date_input(today) or datetime.today().date()

        start_of_week = today_date - timedelta(days=today_date.weekday())

        end_of_week = start_of_week + timedelta(days=6)

        total_minutes = 0

        for record in records:

            record_date = InsightService._parse_record_date(record.date)

            if record_date is None:
                continue

            if start_of_week <= record_date <= end_of_week:
                total_minutes += record.duration_minutes

        return total_minutes

    @staticmethod
    def get_top_subject(records):

        # Tìm môn học có tổng thời gian học cao nhất
        subject_totals = InsightService.get_subject_distribution(records)

        if not subject_totals:
            return ""

        return max(subject_totals, key=subject_totals.get)

    @staticmethod
    def get_subject_distribution(records):

        # Gom tổng phút học theo từng môn
        # Ví dụ: {"Math": 120, "English": 90}
        subject_totals = defaultdict(int)

        for record in records:

            if record.subject:
                subject_totals[record.subject] += record.duration_minutes

        return dict(subject_totals)

    # ============================================================
    # STREAK / GOAL KPI
    # Các hàm tính chuỗi ngày học và mức độ hoàn thành mục tiêu.
    # ============================================================

    @staticmethod
    def get_streak(records, today=None):

        # Tính streak học liên tiếp tính ngược từ hôm nay
        # Nếu hôm nay và hôm qua có học, hôm kia không học => streak = 2
        study_dates = InsightService._get_unique_study_dates(records)

        if not study_dates:
            return 0

        current_day = InsightService._normalize_date_input(today) or datetime.today().date()

        streak = 0

        while current_day in study_dates:

            streak += 1

            current_day -= timedelta(days=1)

        return streak

    @staticmethod
    def get_best_streak(records):

        # Tính chuỗi ngày học liên tiếp dài nhất từng đạt được
        study_dates = sorted(InsightService._get_unique_study_dates(records))

        if not study_dates:
            return 0

        best_streak = 1

        current_streak = 1

        for index in range(1, len(study_dates)):

            if study_dates[index] - study_dates[index - 1] == timedelta(days=1):

                current_streak += 1

            else:

                best_streak = max(best_streak, current_streak)

                current_streak = 1

        return max(best_streak, current_streak)

    @staticmethod
    def get_goal_progress(records, goal_minutes_per_day: int, today=None):

        # Tính % hoàn thành mục tiêu ngày
        # Ví dụ: học 60 phút / mục tiêu 120 phút => 50%
        total_today = InsightService.get_total_minutes_today(records, today=today)

        if goal_minutes_per_day <= 0:
            return 0

        return round((total_today / goal_minutes_per_day) * 100, 1)

    @staticmethod
    def get_remaining_minutes_today(records, goal_minutes_per_day: int, today=None):

        # Tính số phút còn thiếu để đạt mục tiêu ngày
        # Nếu đã vượt mục tiêu thì trả về 0
        if goal_minutes_per_day <= 0:
            return 0

        total_today = InsightService.get_total_minutes_today(records, today=today)

        return max(0, goal_minutes_per_day - total_today)

    @staticmethod
    def count_goal_days_this_week(records, goal_minutes_per_day: int, today=None):

        # Đếm số ngày trong tuần hiện tại đạt đủ mục tiêu học
        if goal_minutes_per_day <= 0:
            return 0

        today_date = InsightService._normalize_date_input(today) or datetime.today().date()

        start_of_week = today_date - timedelta(days=today_date.weekday())

        end_of_week = start_of_week + timedelta(days=6)

        daily_minutes = InsightService.get_daily_totals(records)

        goal_days = 0

        current_day = start_of_week

        while current_day <= end_of_week:

            date_text = current_day.strftime("%Y-%m-%d")

            if daily_minutes.get(date_text, 0) >= goal_minutes_per_day:
                goal_days += 1

            current_day += timedelta(days=1)

        return goal_days

    @staticmethod
    def get_average_minutes_per_study_day(records):

        # Tính trung bình phút học trên mỗi ngày có học
        daily_totals = InsightService.get_daily_totals(records)

        if not daily_totals:
            return 0

        return round(sum(daily_totals.values()) / len(daily_totals), 1)

    # ============================================================
    # DAILY DATA / TREND
    # Các hàm gom dữ liệu theo ngày để phục vụ biểu đồ.
    # ============================================================

    @staticmethod
    def get_daily_totals(records):

        # Gom tổng phút học theo từng ngày
        # Ví dụ: {"2026-05-10": 120, "2026-05-11": 90}
        daily_totals = defaultdict(int)

        for record in records:

            record_date = InsightService._parse_record_date(record.date)

            if record_date is None:
                continue

            date_text = record_date.strftime("%Y-%m-%d")

            daily_totals[date_text] += record.duration_minutes

        return dict(daily_totals)

    @staticmethod
    def get_daily_trend(records, days: int = 7, today=None):

        # Tạo dữ liệu trend trong N ngày gần nhất
        # Dùng cho biểu đồ cột/đường trên Statistics
        if days <= 0:
            return []

        today_date = InsightService._normalize_date_input(today) or datetime.today().date()

        daily_totals = InsightService.get_daily_totals(records)

        trend = []

        for offset in range(days - 1, -1, -1):

            date_item = today_date - timedelta(days=offset)

            date_text = date_item.strftime("%Y-%m-%d")

            trend.append(
                {
                    "date": date_text,
                    "minutes": daily_totals.get(date_text, 0),
                }
            )

        return trend

    @staticmethod
    def get_recent_activity_summary(records, limit: int = 5):

        # Lấy một số record gần đây để hiển thị Recent Activity
        # Sort theo ngày và ID để record mới nhất lên đầu
        sorted_records = sorted(
            records,
            key=lambda record: (
                InsightService._parse_record_date(record.date) or datetime.min.date(),
                record.id,
            ),
            reverse=True,
        )

        return sorted_records[: max(0, int(limit))]

    # ============================================================
    # SUGGESTIONS
    # Tạo câu gợi ý ngắn dựa trên dữ liệu học tập.
    # ============================================================

    @staticmethod
    def generate_suggestions(records, goal_minutes_per_day: int = 120):

        # Tạo danh sách gợi ý hiển thị trên Dashboard
        if not records:
            return [
                "No study data yet. Add your first record to start tracking."
            ]

        suggestions = []

        today_minutes = InsightService.get_total_minutes_today(records)

        top_subject = InsightService.get_top_subject(records)

        subject_totals = InsightService.get_subject_distribution(records)

        if top_subject:
            suggestions.append(
                f"{top_subject} currently takes the most study time."
            )

        if goal_minutes_per_day > 0 and today_minutes < goal_minutes_per_day:

            missing_minutes = goal_minutes_per_day - today_minutes

            suggestions.append(
                f"You still need {missing_minutes} more minutes to reach today's goal."
            )

        if len(subject_totals) >= 2:

            weakest_subject = min(subject_totals, key=subject_totals.get)

            suggestions.append(
                f"{weakest_subject} is getting less study time, so consider adding a short session."
            )

        if not suggestions:
            suggestions.append(
                "Your study progress is stable. Keep up the current rhythm."
            )

        return suggestions

    # ============================================================
    # INTERNAL HELPERS
    # Các hàm phụ để parse ngày và chuẩn hóa input ngày.
    # ============================================================

    @staticmethod
    def _get_unique_study_dates(records):

        # Lấy tập hợp các ngày có học
        study_dates = set()

        for record in records:

            record_date = InsightService._parse_record_date(record.date)

            if record_date is not None:
                study_dates.add(record_date)

        return study_dates

    @staticmethod
    def _parse_record_date(date_text: str):

        # Parse ngày của record từ chuỗi YYYY-MM-DD sang object date
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").date()

        except ValueError:
            return None

    @staticmethod
    def _normalize_today_text(today=None):

        # Chuẩn hóa ngày hôm nay về dạng text YYYY-MM-DD
        normalized_date = InsightService._normalize_date_input(today)

        if normalized_date is None:
            normalized_date = datetime.today().date()

        return normalized_date.strftime("%Y-%m-%d")

    @staticmethod
    def _normalize_date_input(value=None):

        # Chuẩn hóa input ngày.
        # Hỗ trợ datetime, date, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY.
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date()

        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value

        value = str(value).strip()

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):

            try:
                return datetime.strptime(value, fmt).date()

            except ValueError:
                continue

        return None