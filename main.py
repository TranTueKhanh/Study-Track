# ============================================================
# FILE: main.py
# Vai trò: file điều phối chính của ứng dụng Study Track.
# Quản lý giao diện, đăng nhập, timer, lịch sử, thống kê và profile.
# ============================================================

# Thư viện hệ thống dùng cho lỗi, luồng chạy, thời gian và đường dẫn.
import sys
import signal
import inspect
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# PyQt6 dùng để dựng giao diện, xử lý signal/slot và load file .ui.
from PyQt6 import QtCore, QtGui, QtWidgets, uic
# QtCharts là phần tùy chọn; nếu máy chưa cài thì app vẫn chạy, chỉ tắt biểu đồ.
try:
    from PyQt6 import QtCharts
except ImportError:
    QtCharts = None

# Các module nội bộ của dự án: lưu dữ liệu, phân tích học tập và quản lý user.
from data import data_io
from models.insight_service import InsightService
from models.study_database import StudyDatabase
from models.user_manager import UserManager

# Thư mục gốc của file này, dùng để tìm các file .ui và tài nguyên đi kèm.
BASE_DIR = Path(__file__).resolve().parent

# Đóng app an toàn khi người dùng nhấn Ctrl+C trong terminal.
def _handle_keyboard_interrupt(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
        return
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# ============================================================
# BASE PAGE
# Controller nền cho các page nhỏ, gom logic báo lỗi và phát signal.
# ============================================================
class BasePage(QtCore.QObject):
    # Signal báo MainWindow chuyển sang route khác, ví dụ login -> register.
    requestNavigate = QtCore.pyqtSignal(str)
    # Signal gửi dữ liệu/action từ page con lên MainWindow xử lý.
    requestStateChange = QtCore.pyqtSignal(dict)

    # Khởi tạo đối tượng và thiết lập trạng thái ban đầu.
    def __init__(self, page_window: QtWidgets.QMainWindow):
        super().__init__()

        # self.window/self.ui giữ lại page đang điều khiển để các hàm con dùng chung.
        self.window = page_window
        self.ui = page_window

    # Hiện lỗi theo dạng popup để app không im lặng khi thao tác thất bại.
    def _report_error(self, context: str, error: Exception):
        traceback.print_exc()
        try:
            message_box = QtWidgets.QMessageBox(self.window)
            message_box.setWindowTitle("Application Error")
            message_box.setText(f"{context}: {error}")
            message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            message_box.setStyleSheet(
                """
                QMessageBox, QInputDialog {
                    background-color: #FFFFFF;
                }
                QMessageBox QLabel, QInputDialog QLabel {
                    color: #1F2933;
                    font-size: 13px;
                }
                QMessageBox QPushButton, QInputDialog QPushButton {
                    background-color: #FF6B6B;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 14px;
                    min-width: 70px;
                }
                QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
                    background-color: #E85A5A;
                }
                """
            )
            message_box.exec()
        except Exception:
            pass

    # Bọc signal handler để lỗi trong nút bấm không làm crash toàn app.
    # Phần này cũng tự cắt số tham số cho khớp với handler.
    def _connect_safe(self, signal, handler, context: str):
        try:
            signature = inspect.signature(handler)
            parameter_count = len(
                [
                    parameter
                    for parameter in signature.parameters.values()
                    if parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                ]
            )
            has_varargs = any(
                parameter.kind == inspect.Parameter.VAR_POSITIONAL
                for parameter in signature.parameters.values()
            )
        except (TypeError, ValueError):
            parameter_count = 0
            has_varargs = True

        # Bọc hàm gốc để bắt lỗi và truyền đúng tham số cần thiết.
        def wrapped(*args, **kwargs):
            try:
                if has_varargs:
                    return handler(*args, **kwargs)
                return handler(*args[:parameter_count])
            except Exception as error:
                self._report_error(context, error)
                return None

        signal.connect(wrapped)

# ============================================================
# LOGIN PAGE
# Lấy dữ liệu đăng nhập và gửi yêu cầu lên MainWindow.
# ============================================================
class LoginPage(BasePage):
    # Kết nối các widget của giao diện với hàm xử lý tương ứng.
    def wire(self):
        self.login_button = self.ui.findChild(QtWidgets.QPushButton, "loginBtn")
        self.register_button = self.ui.findChild(QtWidgets.QPushButton, "registerBtn")
        self.username_input = self.ui.findChild(QtWidgets.QLineEdit, "usernameInput")
        self.password_input = self.ui.findChild(QtWidgets.QLineEdit, "passwordInput")

        if self.register_button is not None:
            self._connect_safe(
                self.register_button.clicked,
                lambda _checked=False: self.requestNavigate.emit("register"),
                "Open register page",
            )

        if self.login_button is not None:
            self._connect_safe(
                self.login_button.clicked,
                self._emit_login,
                "Login submit",
            )

    # Lấy dữ liệu login từ form và gửi lên MainWindow xử lý.
    def _emit_login(self):
        username = (
            self.username_input.text().strip() if self.username_input is not None else ""
        )
        password = (
            self.password_input.text().strip() if self.password_input is not None else ""
        )
        self.requestStateChange.emit(
            {
                "action": "login",
                "username": username,
                "password": password,
            }
        )

# ============================================================
# REGISTER PAGE
# Lấy dữ liệu đăng ký và gửi yêu cầu lên MainWindow.
# ============================================================
class RegisterPage(BasePage):
    # Kết nối các widget của giao diện với hàm xử lý tương ứng.
    def wire(self):
        self.register_button = self.ui.findChild(QtWidgets.QPushButton, "registerBtn")
        self.go_login_button = self.ui.findChild(QtWidgets.QPushButton, "gologinBtn")
        self.username_input = self.ui.findChild(QtWidgets.QLineEdit, "InputUsername")
        self.password_input = self.ui.findChild(QtWidgets.QLineEdit, "InputPassword")
        self.confirm_input = self.ui.findChild(
            QtWidgets.QLineEdit, "InputConfirmPassword"
        )
        self.agree_check = self.ui.findChild(QtWidgets.QCheckBox, "AgreeCheck")

        if self.go_login_button is not None:
            self._connect_safe(
                self.go_login_button.clicked,
                lambda _checked=False: self.requestNavigate.emit("login"),
                "Open login page",
            )

        if self.register_button is not None:
            self._connect_safe(
                self.register_button.clicked,
                self._emit_register,
                "Register submit",
            )

    # Lấy dữ liệu đăng ký từ form và gửi lên MainWindow xử lý.
    def _emit_register(self):
        username = (
            self.username_input.text().strip() if self.username_input is not None else ""
        )
        password = (
            self.password_input.text().strip() if self.password_input is not None else ""
        )
        confirm_password = (
            self.confirm_input.text().strip() if self.confirm_input is not None else ""
        )
        agreed = self.agree_check.isChecked() if self.agree_check is not None else False

        self.requestStateChange.emit(
            {
                "action": "register",
                "username": username,
                "password": password,
                "confirm_password": confirm_password,
                "agreed": agreed,
            }
        )

# ============================================================
# MAIN WINDOW
# App controller chính: load page, điều hướng và nối UI với dữ liệu.
# ============================================================
class MainWindow(QtWidgets.QMainWindow):
    # Signal dùng để hiện lỗi runtime từ nhiều nơi về luồng giao diện chính.
    runtime_error_signal = QtCore.pyqtSignal(str, str)

    # Khởi tạo đối tượng và thiết lập trạng thái ban đầu.
    def __init__(self):
        super().__init__()

        # Lưu widget trung tâm của từng page theo route.
        self.pages = {}
        # Lưu QMainWindow gốc của từng file .ui để lấy title/style/size.
        self.page_windows = {}
        # Lưu controller con như LoginPage, RegisterPage.
        self.page_controllers = {}
        # QStackedWidget giống một chồng màn hình; mỗi lần chỉ hiện một page.
        self.page_stack = QtWidgets.QStackedWidget(self)
        # Giữ tham chiếu popup đang mở để tránh bị Python dọn rác quá sớm.
        self._open_message_boxes = []

        # State của phiên chạy hiện tại: route, record đang chọn và cờ sync form.
        self.current_route = None
        self.current_record_id = None
        self.selected_history_record_id = None
        self._crud_time_sync_in_progress = False
        self.setCentralWidget(self.page_stack)
        self.runtime_error_signal.connect(self._show_runtime_error_message)

        # QTimer chạy mỗi giây để cập nhật đồng hồ học tập.
        self.session_timer = QtCore.QTimer(self)
        self.session_timer.setInterval(1000)
        self.session_timer.timeout.connect(
            self._make_safe_handler(self.tick_session_timer, "Session timer")
        )
        # State của phiên học hiện tại.
        self.session_elapsed_seconds = 0
        self.session_pause_count = 0
        self.session_is_running = False
        self.session_has_started = False
        self.session_start_datetime = None

        # Các widget Statistics được lazy-init vì phụ thuộc vào UI đã load xong.
        self.statistics_pie_chart_view = None
        self.statistics_bar_chart_view = None
        self.statistics_scroll_area = None
        self.statistics_scroll_content = None
        self.statistics_legend_scroll_area = None
        self.statistics_legend_container = None
        self.statistics_legend_layout = None
        self.statistics_goal_scroll_area = None
        self.statistics_goal_container = None
        self.statistics_goal_layout = None

        # Các widget động của Profile để nhập goal theo subject.
        self.profile_subject_scroll_area = None
        self.profile_subject_container = None
        self.profile_subject_form_layout = None
        self.profile_subject_goal_inputs = {}

        # Hai service chính: user/settings và database record học tập.
        self.user_manager = UserManager()
        self.study_database = StudyDatabase()

        # self.current_user giữ user đang đăng nhập để các màn biết cần đọc dữ liệu của ai.
        self.current_user = (
            self.user_manager.get_remembered_user()
            or self.user_manager.get_last_logged_in_user()
        )

        # Map route -> file .ui. Route là tên nội bộ dùng khi điều hướng.
        self.page_order = {
            "login": "ui/login.ui",
            "register": "ui/register.ui",
            "dashboard": "ui/dashboard.ui",
            "session": "ui/studysession.ui",
            "history": "ui/history.ui",
            "crud": "ui/crud.ui",
            "statistics": "ui/statistics.ui",
            "profile": "ui/profilesetting.ui",
        }

        # Startup được chia nhỏ để một bước lỗi vẫn báo được context rõ ràng.
        self._install_global_exception_hooks()
        self._run_startup_step("Load pages", self._load_pages)
        self._run_startup_step("Setup auth pages", self._setup_auth_pages)
        self._run_startup_step("Setup dashboard", self._setup_dashboard_actions)
        self._run_startup_step("Setup session", self._setup_session_actions)
        self._run_startup_step("Setup CRUD", self._setup_crud_actions)
        self._run_startup_step("Setup history", self._setup_history_actions)
        self._run_startup_step("Setup statistics", self._setup_statistics_actions)
        self._run_startup_step("Setup profile", self._setup_profile_actions)
        self._run_startup_step(
            "Initial navigation",
            lambda: self.navigate(self._get_start_route()),
        )

    # ============================================================
    # AUTHENTICATION
    # Kết nối màn Login/Register với logic xử lý tài khoản.
    # ============================================================
    def _setup_auth_pages(self):
        login_controller = LoginPage(self.pages["login"])
        register_controller = RegisterPage(self.pages["register"])

        self.page_controllers["login"] = login_controller
        self.page_controllers["register"] = register_controller

        for controller in self.page_controllers.values():
            self._connect_safe(controller.requestNavigate, self.navigate, "Navigation request")
            self._connect_safe(controller.requestStateChange, self.handle_action, "Auth action")
            controller.wire()

        login_register_button = self.pages["login"].findChild(
            QtWidgets.QPushButton, "registerBtn"
        )
        if login_register_button is not None:
            self._connect_safe(
                login_register_button.clicked,
                lambda _checked=False: self.navigate("register"),
                "Open register page",
            )

        register_login_button = self.pages["register"].findChild(
            QtWidgets.QPushButton, "gologinBtn"
        )
        if register_login_button is not None:
            self._connect_safe(
                register_login_button.clicked,
                lambda _checked=False: self.navigate("login"),
                "Open login page",
            )

        forgot_button = self.pages["login"].findChild(QtWidgets.QPushButton, "forgotBtn")
        if forgot_button is not None:
            self._connect_safe(
                forgot_button.clicked,
                self.show_forgot_password_message,
                "Forgot password",
            )

        self._setup_auth_feedback()

    # Chuẩn bị label báo lỗi và tự xóa lỗi khi người dùng nhập lại.
    def _setup_auth_feedback(self):
        login_page = self.pages.get("login")
        register_page = self.pages.get("register")

        if login_page is not None:
            error_label = login_page.findChild(QtWidgets.QLabel, "errorLabel")
            if error_label is not None:
                error_label.hide()

            for object_name in ("usernameInput", "passwordInput"):
                widget = login_page.findChild(QtWidgets.QLineEdit, object_name)
                if widget is not None:
                    self._connect_safe(
                        widget.textChanged,
                        lambda _text="": self.clear_login_message(),
                        "Clear login message",
                    )

        if register_page is not None:
            message_label = register_page.findChild(QtWidgets.QLabel, "registerMessageLabel")
            if message_label is None:
                message_label = QtWidgets.QLabel(register_page)
                message_label.setObjectName("registerMessageLabel")
                message_label.setGeometry(44, 328, 540, 24)
                message_label.setStyleSheet(
                    "color:#C94A4A; font-size:12px; font-weight:600; background:transparent;"
                )
                message_label.setWordWrap(True)
            message_label.hide()

            for object_name in ("InputUsername", "InputPassword", "InputConfirmPassword"):
                widget = register_page.findChild(QtWidgets.QLineEdit, object_name)
                if widget is not None:
                    self._connect_safe(
                        widget.textChanged,
                        lambda _text="": self.clear_register_message(),
                        "Clear register message",
                    )

            agree_check = register_page.findChild(QtWidgets.QCheckBox, "AgreeCheck")
            if agree_check is not None:
                self._connect_safe(
                    agree_check.stateChanged,
                    lambda _state=0: self.clear_register_message(),
                    "Clear register message",
                )

    # Chọn màn hình đầu tiên: có user thì vào dashboard, chưa có thì vào login.
    def _get_start_route(self):
        if self.current_user is not None:
            return "dashboard"
        return "login"

    # Điều phối action từ Login/Register đến đúng hàm xử lý.
    @QtCore.pyqtSlot(dict)
    # Điều phối action do LoginPage/RegisterPage gửi lên.
    def handle_action(self, payload: dict):
        action = payload.get("action")

        if action == "login":
            self.handle_login(payload)
            return

        if action == "register":
            self.handle_register(payload)

    # Xử lý đăng nhập: validate form, gọi UserManager, báo lỗi hoặc vào dashboard.
    def handle_login(self, payload: dict):
        login_page = self.pages.get("login")
        if login_page is None:
            return

        username_input = login_page.findChild(QtWidgets.QLineEdit, "usernameInput")
        password_input = login_page.findChild(QtWidgets.QLineEdit, "passwordInput")
        error_label = login_page.findChild(QtWidgets.QLabel, "errorLabel")

        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()

        if error_label is not None:
            error_label.hide()

        if not username or not password:
            self._show_message("Login", "Please enter both username and password.")
            if error_label is not None:
                error_label.setText("Please enter both username and password.")
                error_label.show()
            return

        try:
            self.current_user = self.user_manager.login_user(
                username,
                password,
                remember_me=True,
            )
        except ValueError as error:
            self._show_message("Login", str(error), icon="warning")
            if error_label is not None:
                error_label.setText(str(error))
                error_label.show()
            return

        if username_input is not None:
            username_input.clear()
        if password_input is not None:
            password_input.clear()

        self._show_message("Login", "Login successful.", icon="info")
        self.navigate("dashboard")

    # Xử lý đăng ký: kiểm tra dữ liệu, tạo user mới rồi quay về login.
    def handle_register(self, payload: dict):
        register_page = self.pages.get("register")
        if register_page is None:
            return

        username_input = register_page.findChild(QtWidgets.QLineEdit, "InputUsername")
        password_input = register_page.findChild(QtWidgets.QLineEdit, "InputPassword")
        confirm_input = register_page.findChild(
            QtWidgets.QLineEdit, "InputConfirmPassword"
        )
        agree_check = register_page.findChild(QtWidgets.QCheckBox, "AgreeCheck")

        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()
        confirm_password = (payload.get("confirm_password") or "").strip()
        agreed = bool(payload.get("agreed"))

        if not username or not password or not confirm_password:
            self._show_message("Register", "Please fill in all required fields.")
            return

        if not agreed:
            self._show_message(
                "Register",
                "You must agree to the terms before registering.",
            )
            return

        try:
            self.user_manager.register_user(username, password, confirm_password)
        except ValueError as error:
            self._show_message("Register", str(error), icon="warning")
            return

        if username_input is not None:
            username_input.clear()
        if password_input is not None:
            password_input.clear()
        if confirm_input is not None:
            confirm_input.clear()
        if agree_check is not None:
            agree_check.setChecked(False)

        self._show_message(
            "Register",
            "Registration successful. You can log in now.",
            icon="info",
        )
        self.navigate("login")

    # Hiện thông báo tính năng quên mật khẩu chưa khả dụng.
    def show_forgot_password_message(self):
        self._show_message(
            "Forgot Password",
            "The forgot password feature is not available yet.",
            icon="info",
        )

    # Xóa thông báo lỗi ở màn hình đăng nhập.
    def clear_login_message(self):
        login_page = self.pages.get("login")
        if login_page is None:
            return

        error_label = login_page.findChild(QtWidgets.QLabel, "errorLabel")
        if error_label is not None:
            error_label.clear()
            error_label.hide()

    # Xóa thông báo lỗi ở màn hình đăng ký.
    def clear_register_message(self):
        register_page = self.pages.get("register")
        if register_page is None:
            return

        message_label = register_page.findChild(QtWidgets.QLabel, "registerMessageLabel")
        if message_label is not None:
            message_label.clear()
            message_label.hide()

    # ============================================================
    # DASHBOARD
    # Gắn nút dashboard và nạp KPI/tóm tắt học tập.
    # ============================================================
    
    # Gắn sự kiện cho các nút và action trên Dashboard.
    def _setup_dashboard_actions(self):
        dashboard_page = self.pages.get("dashboard")
        if dashboard_page is None:
            return

        # objectName của nút dashboard -> route đích.
        button_route_map = {
            "BtnStartSession": "session",
            "BtnQuickAddRecord": "crud",
            "BtnViewStats": "statistics",
            "BtnReviewPlan": "statistics",
            "BtnOpenSessionTip": "session",
            "BtnApplySuggestion": "session",
        }

        for button_name, route in button_route_map.items():
            button = dashboard_page.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(
                    button.clicked,
                    self._make_navigation_handler(route),
                    f"Dashboard button {button_name}",
                )

    # Nạp phần header và lời chào của Dashboard.
    def load_dashboard_header(self):
        dashboard_page = self.pages.get("dashboard")
        if dashboard_page is None:
            return

        lbl_greeting = dashboard_page.findChild(QtWidgets.QLabel, "lblGreeting")
        lbl_date_today = dashboard_page.findChild(QtWidgets.QLabel, "lblDateToday")

        username = self._get_current_user_label()

        if lbl_greeting is not None:
            lbl_greeting.setText(f"Hello, {username}")

        if lbl_date_today is not None:
            lbl_date_today.setText(datetime.now().strftime("%d/%m/%Y"))

    # Lấy record của user, tính KPI qua InsightService rồi đổ ra giao diện.
    def load_dashboard_data(self):
        dashboard_page = self.pages.get("dashboard")
        if dashboard_page is None or self.current_user is None:
            return

        records = self.study_database.get_records_by_username(self.current_user.username)
        goal_minutes = int(getattr(self.current_user, "goal_minutes_per_day", 120))

        today_minutes = InsightService.get_total_minutes_today(records)
        week_minutes = InsightService.get_total_minutes_this_week(records)
        streak = InsightService.get_streak(records)
        best_streak = InsightService.get_best_streak(records)
        top_subject = InsightService.get_top_subject(records)
        goal_progress = InsightService.get_goal_progress(records, goal_minutes)
        remaining_minutes = InsightService.get_remaining_minutes_today(records, goal_minutes)
        goal_days = InsightService.count_goal_days_this_week(records, goal_minutes)
        average_minutes = InsightService.get_average_minutes_per_study_day(records)
        suggestions = InsightService.generate_suggestions(records, goal_minutes)
        recent_records = InsightService.get_recent_activity_summary(records)
        subject_distribution = InsightService.get_subject_distribution(records)

        top_subject_share = 0
        if top_subject and subject_distribution:
            total_subject_minutes = sum(subject_distribution.values())
            if total_subject_minutes > 0:
                top_subject_share = round(
                    (subject_distribution.get(top_subject, 0) / total_subject_minutes) * 100
                )

        self._set_label_text(dashboard_page, "lblTodayValue", self._format_minutes_short(today_minutes))
        self._set_label_text(dashboard_page, "lblWeekValue", self._format_minutes_short(week_minutes))
        self._set_label_text(dashboard_page, "lblStreakValue", f"{streak} days")
        self._set_label_text(dashboard_page, "lblTopSubjectValue", top_subject or "No data")
        self._set_label_text(dashboard_page, "lblGoalProgressText", f"{today_minutes} / {goal_minutes} minutes")
        self._set_label_text(dashboard_page, "lblGoalRemaining", f"{remaining_minutes} minutes left to reach today's goal")
        self._set_label_text(dashboard_page, "lblWeekSub", f"Average {self._format_minutes_short(average_minutes)} per study day")
        self._set_label_text(dashboard_page, "lblStreakSub", f"Best streak: {best_streak} days")
        self._set_label_text(dashboard_page, "lblTopSubjectSub", f"Takes {top_subject_share}% of total study time")
        self._set_label_text(dashboard_page, "lblSidebarStatusValue", f"{int(goal_progress)}%")
        self._set_label_text(
            dashboard_page,
            "lblSidebarStatusSub",
            "You are close to today's study goal." if goal_progress >= 60 else "Keep going to reach today's study goal.",
        )
        self._set_label_text(
            dashboard_page,
            "lblHeroSideBody",
            f"You reached your goal on {goal_days}/7 days, and {top_subject or 'no subject yet'} stands out this week.",
        )
        self._set_label_text(dashboard_page, "lblInsightBody", suggestions[0] if suggestions else "No suggestions yet.")

        progress_bar = dashboard_page.findChild(QtWidgets.QProgressBar, "progressDailyGoal")
        if progress_bar is not None:
            progress_bar.setValue(max(0, min(100, int(goal_progress))))

        recent_list = dashboard_page.findChild(QtWidgets.QListWidget, "listRecentRecords")
        if recent_list is not None:
            recent_list.clear()
            if not recent_records:
                recent_list.addItem("No recent activity.")
            else:

                for record in recent_records:
                    recent_list.addItem(
                        f"{record.date} - {record.subject}: {record.content} ({record.duration_minutes} min)"
                    )

    # ============================================================
    # STUDY SESSION
    # Quản lý timer, subject/mode và luồng kết thúc phiên học.
    # ============================================================
    
    # Gắn các action cho màn hình Study Session.
    def _setup_session_actions(self):
        session_page = self.pages.get("session")
        if session_page is None:
            return

        # objectName của nút -> hàm xử lý tương ứng.
        action_map = {
            "btnBackDashboard": self._make_navigation_handler("dashboard"),
            "btnStartTimer": self.start_session_timer,
            "btnPauseTimer": self.pause_session_timer,
            "btnResumeTimer": self.resume_session_timer,
            "btnEndSession": self.end_session_to_crud,
            "btnQuickEndToCrud": self.preview_session_to_crud,
        }

        for button_name, handler in action_map.items():
            button = session_page.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(button.clicked, handler, f"Session button {button_name}")

        for combo_name in ("cmbSessionSubject", "cmbSessionMode"):
            combo = session_page.findChild(QtWidgets.QComboBox, combo_name)
            if combo is not None:
                self._connect_safe(
                    combo.currentTextChanged,
                    self.update_session_ui,
                    f"Session combo {combo_name}",
                )

        self.populate_session_subjects()
        self.reset_session_state()

    # Nạp danh sách subject vào combo của màn Study Session.
    def populate_session_subjects(self):
        session_page = self._get_page_widget("session")
        if session_page is None:
            return

        subject_combo = session_page.findChild(QtWidgets.QComboBox, "cmbSessionSubject")
        if subject_combo is None or self.current_user is None:
            return

        current_text = subject_combo.currentText().strip()
        subject_combo.blockSignals(True)
        subject_combo.clear()
        for subject in self._get_subject_list_for_user():
            subject_combo.addItem(subject)

        index = subject_combo.findText(current_text)
        subject_combo.setCurrentIndex(index if index >= 0 else 0)
        subject_combo.blockSignals(False)

    # Đưa timer và UI phiên học về trạng thái ban đầu.
    def reset_session_state(self):
        self.session_timer.stop()
        # State của phiên học hiện tại.
        self.session_elapsed_seconds = 0
        self.session_pause_count = 0
        self.session_is_running = False
        self.session_has_started = False
        self.session_start_datetime = None
        self.update_session_ui()

    # Nạp dữ liệu khi mở màn hình Session.
    def load_session_page(self):
        self.populate_session_subjects()
        self.update_session_ui()

    # Mỗi giây tăng bộ đếm và cập nhật đồng hồ trên màn Session.
    def tick_session_timer(self):
        if not self.session_is_running:
            return

        self.session_elapsed_seconds += 1
        self.update_session_ui()

    # Bắt đầu phiên học: khóa thông tin đầu vào cần thiết và chạy QTimer.
    def start_session_timer(self):
        if self.session_is_running:
            return

        if self.current_user is None:
            self._show_message("Study Session", "You need to log in first.")
            return

        self.populate_session_subjects()
        session_page = self._get_page_widget("session")
        subject_combo = (
            session_page.findChild(QtWidgets.QComboBox, "cmbSessionSubject")
            if session_page is not None
            else None
        )
        if subject_combo is None or not subject_combo.currentText().strip():
            self._show_message("Study Session", "Please choose a subject before starting.", icon="warning")
            return

        # State của phiên học hiện tại.
        self.session_elapsed_seconds = 0
        self.session_pause_count = 0
        self.session_is_running = True
        self.session_has_started = True
        self.session_start_datetime = datetime.now()
        self.session_timer.start()
        self.update_session_ui()

    # Tạm dừng timer nhưng vẫn giữ thời gian đã học.
    def pause_session_timer(self):
        if not self.session_is_running:
            return

        self.session_timer.stop()
        self.session_is_running = False
        self.session_pause_count += 1
        self.update_session_ui()

    # Chạy tiếp timer sau khi pause.
    def resume_session_timer(self):
        if not self.session_has_started or self.session_is_running:
            return

        self.session_is_running = True
        self.session_timer.start()
        self.update_session_ui()

    # Kết thúc phiên học và chuyển dữ liệu sang form CRUD để lưu record.
    def end_session_to_crud(self):
        if not self.session_has_started:
            self._show_message(
                "Study Session",
                "Please start a session before pressing End.",
                icon="warning",
            )
            return

        self.session_timer.stop()
        self.session_is_running = False
        self.open_crud_with_session_data(from_timer=True)
        self.reset_session_state()

    # Mở CRUD với dữ liệu session hiện tại.
    def preview_session_to_crud(self):
        self.open_crud_with_session_data(from_timer=self.session_has_started)

    # Chuyển dữ liệu session sang form CRUD.
    def open_crud_with_session_data(self, from_timer: bool = False):
        crud_page = self._get_page_widget("crud")
        session_page = self._get_page_widget("session")
        if crud_page is None or session_page is None:
            return

        self.current_record_id = None
        self.populate_crud_subjects()
        self.reset_crud_form()

        session_subject = session_page.findChild(QtWidgets.QComboBox, "cmbSessionSubject")
        session_mode = session_page.findChild(QtWidgets.QComboBox, "cmbSessionMode")

        subject_text = session_subject.currentText().strip() if session_subject is not None else ""
        mode_text = session_mode.currentText().strip() if session_mode is not None else "Focus"
        now = datetime.now()
        start_dt = self.session_start_datetime or now
        duration_seconds = max(0, int(self.session_elapsed_seconds))
        duration_minutes = (
            self._normalize_session_duration_minutes(duration_seconds)
            if from_timer
            else int(self.user_manager.load_settings().get("default_session_length", 45))
        )
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        subject_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbSubject")
        date_edit = crud_page.findChild(QtWidgets.QDateEdit, "dateStudyDate")
        tag_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbTag")
        duration_spin = crud_page.findChild(QtWidgets.QSpinBox, "spinDuration")
        start_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeStart")
        end_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd")
        content_text = crud_page.findChild(QtWidgets.QTextEdit, "txtStudyContent")
        note_text = crud_page.findChild(QtWidgets.QTextEdit, "txtNote")

        if subject_combo is not None:
            index = subject_combo.findText(subject_text)
            if index >= 0:
                subject_combo.setCurrentIndex(index)
        if date_edit is not None:
            date_edit.setDate(QtCore.QDate(start_dt.year, start_dt.month, start_dt.day))
        if tag_combo is not None:
            index = tag_combo.findText(mode_text)
            if index >= 0:
                tag_combo.setCurrentIndex(index)
        if duration_spin is not None:
            duration_spin.setValue(duration_minutes)
        if start_time is not None:
            start_time.setTime(QtCore.QTime(start_dt.hour, start_dt.minute))
        if end_time is not None:
            end_time.setTime(QtCore.QTime(end_dt.hour, end_dt.minute))
        if content_text is not None:
            content_text.clear()
        if note_text is not None:
            note_text.clear()

        self.clear_crud_error()
        self.update_crud_preview()
        self.navigate("crud")

    # Cập nhật giao diện realtime của Session.
    def update_session_ui(self):
        session_page = self._get_page_widget("session")
        if session_page is None:
            return

        subject_combo = session_page.findChild(QtWidgets.QComboBox, "cmbSessionSubject")
        mode_combo = session_page.findChild(QtWidgets.QComboBox, "cmbSessionMode")
        progress_bar = session_page.findChild(QtWidgets.QProgressBar, "progressSessionGoal")

        subject_text = subject_combo.currentText().strip() if subject_combo is not None else "Not selected"
        mode_text = mode_combo.currentText().strip() if mode_combo is not None else "Focus"

        elapsed_minutes = self.session_elapsed_seconds // 60
        elapsed_text = self._format_session_clock(self.session_elapsed_seconds)
        goal_minutes = int(getattr(self.current_user, "goal_minutes_per_day", 120)) if self.current_user is not None else 120
        default_session_length = int(self.user_manager.load_settings().get("default_session_length", 45))
        target_minutes = min(default_session_length, goal_minutes) if goal_minutes > 0 else default_session_length
        progress_value = 0
        if target_minutes > 0:
            progress_value = min(100, int((elapsed_minutes / target_minutes) * 100))

        if self.session_is_running:
            status_text = "Running"
            sidebar_text = "Running"
            sidebar_sub = "The timer is running. You can pause if you need a break."
            badge_text = "Timer running"
        elif self.session_has_started:
            status_text = "Paused"
            sidebar_text = "Paused"
            sidebar_sub = "The session is paused. Press Resume to continue studying."
            badge_text = "Timer paused"
        else:
            status_text = "Ready"
            sidebar_text = "Ready"
            sidebar_sub = "Choose subject and start timer."
            badge_text = "Timer not started"

        self._set_label_text(session_page, "lblGreeting", "Focus Session")
        self._set_label_text(
            session_page,
            "lblDateToday",
            "Choose a subject, start the timer, and move to CRUD after finishing.",
        )
        self._set_label_text(session_page, "lblTimerDisplay", elapsed_text)
        self._set_label_text(session_page, "lblSessionStatus", status_text)
        self._set_label_text(session_page, "lblElapsedValue", f"{elapsed_minutes}m")
        self._set_label_text(session_page, "lblPauseCount", str(self.session_pause_count))
        self._set_label_text(session_page, "lblBadgeTimer", badge_text)
        self._set_label_text(session_page, "lblBadgeFocus", f"{mode_text} ready")
        self._set_label_text(
            session_page,
            "lblProgressText",
            f"{elapsed_minutes} / {target_minutes} minutes session goal",
        )
        self._set_label_text(session_page, "lblSidebarStatusValue", sidebar_text)
        self._set_label_text(session_page, "lblSidebarStatusSub", sidebar_sub)
        smart_hint_text = f"{subject_text} will be sent to CRUD after the session ends."
        focus_tip_text = f"Tip: Study {subject_text} in {mode_text} mode. Take a 5-minute break after 45 minutes."
        self._set_label_text(session_page, "lblSmartHintBody", smart_hint_text)
        self._set_label_text(session_page, "lblFocusTip", focus_tip_text)

        if progress_bar is not None:
            progress_bar.setValue(progress_value)

        start_button = session_page.findChild(QtWidgets.QPushButton, "btnStartTimer")
        pause_button = session_page.findChild(QtWidgets.QPushButton, "btnPauseTimer")
        resume_button = session_page.findChild(QtWidgets.QPushButton, "btnResumeTimer")
        end_button = session_page.findChild(QtWidgets.QPushButton, "btnEndSession")

        if start_button is not None:
            start_button.setEnabled(not self.session_has_started)
        if pause_button is not None:
            pause_button.setEnabled(self.session_is_running)
        if resume_button is not None:
            resume_button.setEnabled(self.session_has_started and not self.session_is_running)
        if end_button is not None:
            end_button.setEnabled(self.session_has_started)

    # ============================================================
    # CRUD RECORD
    # Quản lý form thêm/sửa record và đồng bộ duration với giờ bắt đầu/kết thúc.
    # ============================================================
    
    # Gắn action và signal cho màn hình CRUD.
    def _setup_crud_actions(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        # objectName của nút -> hàm xử lý tương ứng.
        action_map = {
            "btnSaveRecord": self.save_crud_record,
            "btnSaveAndAddNew": self.save_and_reset_crud_form,
            "btnCancelRecord": self._make_navigation_handler("dashboard"),
            "btnDeleteRecord": self.delete_current_crud_record,
            "btnBackHistory": self._make_navigation_handler("history"),
        }

        for button_name, handler in action_map.items():
            button = crud_page.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(button.clicked, handler, f"CRUD button {button_name}")

        date_edit = crud_page.findChild(QtWidgets.QDateEdit, "dateStudyDate")
        if date_edit is not None:
            date_edit.setMaximumDate(QtCore.QDate.currentDate())

        # Các input cần theo dõi để tự cập nhật preview hoặc đồng bộ thời gian.
        watch_widgets = [
            crud_page.findChild(QtWidgets.QComboBox, "cmbSubject"),
            date_edit,
            crud_page.findChild(QtWidgets.QComboBox, "cmbTag"),
            crud_page.findChild(QtWidgets.QSpinBox, "spinDuration"),
            crud_page.findChild(QtWidgets.QTimeEdit, "timeStart"),
            crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd"),
            crud_page.findChild(QtWidgets.QTextEdit, "txtStudyContent"),
            crud_page.findChild(QtWidgets.QTextEdit, "txtNote"),
            crud_page.findChild(QtWidgets.QSlider, "sliderEffectiveness"),
            crud_page.findChild(QtWidgets.QComboBox, "cmbMood"),
        ]

        for widget in watch_widgets:
            if widget is None:
                continue
            if isinstance(widget, QtWidgets.QComboBox):
                self._connect_safe(widget.currentTextChanged, self.update_crud_preview, "CRUD preview")
            elif isinstance(widget, QtWidgets.QDateEdit):
                self._connect_safe(widget.dateChanged, self.update_crud_preview, "CRUD preview")
            elif isinstance(widget, QtWidgets.QSpinBox):
                if widget.objectName() == "spinDuration":
                    self._connect_safe(
                        widget.valueChanged,
                        self._handle_crud_duration_changed,
                        "CRUD duration sync",
                    )
                else:
                    self._connect_safe(widget.valueChanged, self.update_crud_preview, "CRUD preview")
            elif isinstance(widget, QtWidgets.QTimeEdit):
                if widget.objectName() == "timeStart":
                    self._connect_safe(
                        widget.timeChanged,
                        self._handle_crud_start_time_changed,
                        "CRUD start time sync",
                    )
                elif widget.objectName() == "timeEnd":
                    self._connect_safe(
                        widget.timeChanged,
                        self._handle_crud_end_time_changed,
                        "CRUD end time sync",
                    )
                else:
                    self._connect_safe(widget.timeChanged, self.update_crud_preview, "CRUD preview")
            elif isinstance(widget, QtWidgets.QTextEdit):
                self._connect_safe(widget.textChanged, self.update_crud_preview, "CRUD preview")
            elif isinstance(widget, QtWidgets.QSlider):
                self._connect_safe(widget.valueChanged, self.update_crud_preview, "CRUD preview")

        self.populate_crud_subjects()
        self.reset_crud_form()

    # Nạp subject vào form CRUD, giữ lại lựa chọn hiện tại nếu còn tồn tại.
    def populate_crud_subjects(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        subject_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbSubject")
        if subject_combo is None:
            return

        if self.current_user is None:
            return

        current_text = subject_combo.currentText().strip()
        subject_combo.blockSignals(True)
        subject_combo.clear()
        for subject in self._get_subject_list_for_user():
            subject_combo.addItem(subject)

        index = subject_combo.findText(current_text)
        subject_combo.setCurrentIndex(index if index >= 0 else 0)
        subject_combo.blockSignals(False)

    # Đọc toàn bộ dữ liệu người dùng nhập trong form CRUD thành một dict.
    def get_crud_form_data(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return {}

        subject_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbSubject")
        date_edit = crud_page.findChild(QtWidgets.QDateEdit, "dateStudyDate")
        tag_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbTag")
        duration_spin = crud_page.findChild(QtWidgets.QSpinBox, "spinDuration")
        start_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeStart")
        end_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd")
        content_text = crud_page.findChild(QtWidgets.QTextEdit, "txtStudyContent")
        note_text = crud_page.findChild(QtWidgets.QTextEdit, "txtNote")
        effectiveness_slider = crud_page.findChild(QtWidgets.QSlider, "sliderEffectiveness")
        mood_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbMood")

        effectiveness_value = 0
        if effectiveness_slider is not None:

            effectiveness_value = max(0, min(5, round(effectiveness_slider.value() / 2)))

        return {
            "date": date_edit.date().toString("yyyy-MM-dd") if date_edit is not None else "",
            "subject": subject_combo.currentText().strip() if subject_combo is not None else "",
            "content": content_text.toPlainText().strip() if content_text is not None else "",
            "duration_minutes": duration_spin.value() if duration_spin is not None else 0,
            "effectiveness": effectiveness_value,
            "note": note_text.toPlainText().strip() if note_text is not None else "",
            "tag": tag_combo.currentText().strip() if tag_combo is not None else "",
            "start_time": start_time.time().toString("HH:mm") if start_time is not None else "",
            "end_time": end_time.time().toString("HH:mm") if end_time is not None else "",
            "mood": mood_combo.currentText().strip() if mood_combo is not None else "",
        }

    # Lấy các widget liên quan tới thời gian trong CRUD.
    def _get_crud_time_widgets(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return None, None, None

        duration_spin = crud_page.findChild(QtWidgets.QSpinBox, "spinDuration")
        start_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeStart")
        end_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd")
        return duration_spin, start_time, end_time

    # Đồng bộ dữ liệu khi duration thay đổi.
    def _handle_crud_duration_changed(self, _value=None):
        self._sync_crud_time_fields(source="duration")
        self.update_crud_preview()

    # Đồng bộ dữ liệu khi giờ bắt đầu thay đổi.
    def _handle_crud_start_time_changed(self, _time=None):
        self._sync_crud_time_fields(source="start")
        self.update_crud_preview()

    # Đồng bộ dữ liệu khi giờ kết thúc thay đổi.
    def _handle_crud_end_time_changed(self, _time=None):
        self._sync_crud_time_fields(source="end")
        self.update_crud_preview()

    # Đồng bộ duration với giờ bắt đầu/kết thúc.
    # Dùng cờ _crud_time_sync_in_progress để tránh signal gọi lặp vô hạn.
    def _sync_crud_time_fields(self, source: str):

        # self._crud_time_sync_in_progress đánh dấu đang tự sync để signal không gọi vòng lặp.
        if self._crud_time_sync_in_progress:
            return

        duration_spin, start_time, end_time = self._get_crud_time_widgets()
        if duration_spin is None or start_time is None or end_time is None:
            return

        self._crud_time_sync_in_progress = True
        try:
            start_qtime = start_time.time()
            end_qtime = end_time.time()
            duration_minutes = max(0, int(duration_spin.value()))

            if source in {"duration", "start"}:
                end_time.setTime(start_qtime.addSecs(duration_minutes * 60))
                return

            if source == "end":
                start_minutes = start_qtime.hour() * 60 + start_qtime.minute()
                end_minutes = end_qtime.hour() * 60 + end_qtime.minute()
                duration_spin.setValue(max(0, end_minutes - start_minutes))
        finally:
            self._crud_time_sync_in_progress = False

    # Cập nhật preview record trong CRUD.
    def update_crud_preview(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        form_data = self.get_crud_form_data()
        subject = form_data.get("subject") or "No subject selected"
        duration = int(form_data.get("duration_minutes", 0))
        content = form_data.get("content") or "This record will be saved to History after you press Save."

        completion_ready = bool(form_data.get("subject") and form_data.get("content"))

        self._set_label_text(
            crud_page,
            "lblRecordFormTitle",
            "Edit Study Record" if self.current_record_id else "Add Study Record",
        )
        self._set_label_text(crud_page, "lblSummaryTitle", "RECORD PREVIEW")
        self._set_label_text(crud_page, "lblSummaryValue", f"{duration} min - {subject}")
        self._set_label_text(crud_page, "lblSummaryText", content)
        self._set_label_text(crud_page, "lblSummaryBadge", "Ready to validate" if completion_ready else "Draft")
        self._set_label_text(crud_page, "lblSidebarStatusValue", "Ready" if completion_ready else "Draft")
        self._set_label_text(
            crud_page,
            "lblSidebarStatusSub",
            "The form has enough required data to save." if completion_ready else "Fill required fields before saving.",
        )

    # Xóa thông báo lỗi của CRUD form.
    def clear_crud_error(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return
        self._set_label_text(crud_page, "lblFormError", "")

    # Hiển thị lỗi trên CRUD form.
    def show_crud_error(self, message: str):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return
        self._set_label_text(crud_page, "lblFormError", message)

    # Validate form rồi thêm mới hoặc cập nhật record trong database.
    def save_crud_record(self):
        if self.current_user is None:
            self._show_message("CRUD", "You need to log in first.")
            return

        form_data = self.get_crud_form_data()
        self.clear_crud_error()

        try:

            # self.current_record_id rỗng nghĩa là tạo record mới, có ID nghĩa là đang edit.
            if self.current_record_id is None:
                self.study_database.add_record(self.current_user.username, form_data)
            else:
                self.study_database.update_record(
                    self.current_record_id,
                    form_data,
                    username=self.current_user.username,
                )
        except ValueError as error:
            self.show_crud_error(str(error))
            self._show_message("Save Record", str(error), icon="warning")
            return

        self.populate_crud_subjects()
        self.load_dashboard_data()
        self.update_crud_preview()
        self.load_history_data()
        self.current_record_id = None
        self._show_message("Save Record", "Study record saved.", icon="info")

    # Xóa record đang mở trong form CRUD; nếu đang thêm mới thì chỉ xóa form.
    def delete_current_crud_record(self):
        if self.current_user is None:
            self._show_message("CRUD", "You need to log in first.")
            return

        # Nếu form đang ở chế độ thêm mới thì nút Delete chỉ đóng vai trò xóa nháp.
        if self.current_record_id is None:
            self.reset_crud_form()
            return

        # Tìm record đang edit và đảm bảo record đó thuộc đúng user hiện tại.
        record = self.study_database.get_user_record_by_id(
            self.current_user.username,
            self.current_record_id,
        )
        if record is None:
            self._show_message("CRUD", "The current record could not be found.", icon="warning")
            self.current_record_id = None
            self.reset_crud_form()
            return

        # Hỏi xác nhận trước khi xóa dữ liệu thật trong file JSON.
        confirm = self._ask_confirmation(
            "Delete Record",
            "Are you sure you want to delete this record?",
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        # Xóa record, reset trạng thái chọn và refresh các màn đang dùng dữ liệu này.
        self.study_database.delete_record(record.id, username=self.current_user.username)
        self.current_record_id = None
        self.selected_history_record_id = None
        self.reset_crud_form()
        self.load_dashboard_data()
        self.load_history_data()
        self._show_message("CRUD", "Record deleted.", icon="info")

    # Lưu record và reset form để nhập tiếp.
    def save_and_reset_crud_form(self):
        self.save_crud_record()
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        error_label = crud_page.findChild(QtWidgets.QLabel, "lblFormError")
        if error_label is not None and error_label.text().strip():
            return

        self.reset_crud_form()

    # Xóa form CRUD và đưa các giá trị về mặc định.
    def reset_crud_form(self):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        self.current_record_id = None

        default_duration = None

        subject_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbSubject")
        date_edit = crud_page.findChild(QtWidgets.QDateEdit, "dateStudyDate")
        tag_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbTag")
        duration_spin = crud_page.findChild(QtWidgets.QSpinBox, "spinDuration")
        start_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeStart")
        end_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd")
        content_text = crud_page.findChild(QtWidgets.QTextEdit, "txtStudyContent")
        note_text = crud_page.findChild(QtWidgets.QTextEdit, "txtNote")
        effectiveness_slider = crud_page.findChild(QtWidgets.QSlider, "sliderEffectiveness")
        mood_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbMood")

        if duration_spin is not None:
            default_duration = duration_spin.value()

        if subject_combo is not None and subject_combo.count() > 0:
            subject_combo.setCurrentIndex(0)
        if date_edit is not None:
            date_edit.setDate(QtCore.QDate.currentDate())
        if tag_combo is not None and tag_combo.count() > 0:
            tag_combo.setCurrentIndex(0)
        if duration_spin is not None and default_duration is not None:
            duration_spin.setValue(default_duration)
        current_time = QtCore.QTime.currentTime()
        if start_time is not None:
            start_time.setTime(current_time)
        if end_time is not None:
            duration_value = default_duration if default_duration is not None else 0
            end_time.setTime(current_time.addSecs(max(0, int(duration_value)) * 60))
        if content_text is not None:
            content_text.clear()
        if note_text is not None:
            note_text.clear()
        if effectiveness_slider is not None:
            effectiveness_slider.setValue(7)
        if mood_combo is not None and mood_combo.count() > 0:
            mood_combo.setCurrentIndex(0)

        self.clear_crud_error()
        self.update_crud_preview()

    # Mở CRUD ở chế độ tạo mới record.
    def open_crud_create_mode(self):
        self.reset_crud_form()
        self.navigate("crud")

    # Đổ dữ liệu record có sẵn vào form CRUD.
    def fill_crud_form_from_record(self, record):
        crud_page = self._get_page_widget("crud")
        if crud_page is None:
            return

        self.populate_crud_subjects()

        subject_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbSubject")
        date_edit = crud_page.findChild(QtWidgets.QDateEdit, "dateStudyDate")
        tag_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbTag")
        duration_spin = crud_page.findChild(QtWidgets.QSpinBox, "spinDuration")
        start_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeStart")
        end_time = crud_page.findChild(QtWidgets.QTimeEdit, "timeEnd")
        content_text = crud_page.findChild(QtWidgets.QTextEdit, "txtStudyContent")
        note_text = crud_page.findChild(QtWidgets.QTextEdit, "txtNote")
        effectiveness_slider = crud_page.findChild(QtWidgets.QSlider, "sliderEffectiveness")
        mood_combo = crud_page.findChild(QtWidgets.QComboBox, "cmbMood")

        if subject_combo is not None:
            index = subject_combo.findText(record.subject)
            if index >= 0:
                subject_combo.setCurrentIndex(index)
        if date_edit is not None:
            date_edit.setDate(QtCore.QDate.fromString(record.date, "yyyy-MM-dd"))
        if tag_combo is not None:
            index = tag_combo.findText(record.tag)
            if index >= 0:
                tag_combo.setCurrentIndex(index)
        if duration_spin is not None:
            duration_spin.setValue(record.duration_minutes)
        if start_time is not None and record.start_time:
            start_time.setTime(QtCore.QTime.fromString(record.start_time, "HH:mm"))
        if end_time is not None and record.end_time:
            end_time.setTime(QtCore.QTime.fromString(record.end_time, "HH:mm"))
        if content_text is not None:
            content_text.setPlainText(record.content)
        if note_text is not None:
            note_text.setPlainText(record.note)
        if effectiveness_slider is not None:
            effectiveness_slider.setValue(max(1, min(10, record.effectiveness * 2)))
        if mood_combo is not None:
            index = mood_combo.findText(record.mood)
            if index >= 0:
                mood_combo.setCurrentIndex(index)

        self.clear_crud_error()
        self.update_crud_preview()

    # ============================================================
    # HISTORY
    # Hiển thị, lọc, chọn, sửa và xóa các record học tập.
    # ============================================================
    
    # Gắn action cho màn hình History.
    def _setup_history_actions(self):
        history_page = self.pages.get("history")
        if history_page is None:
            return

        # objectName của nút -> hàm xử lý tương ứng.
        action_map = {
            "btnAddNewRecord": self.open_crud_create_mode,
            "btnEditSelected": self.open_selected_record_for_edit,
            "btnDeleteSelected": self.delete_selected_history_record,
            "btnClearFilter": self.clear_history_filters,
        }

        for button_name, handler in action_map.items():
            button = history_page.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(button.clicked, handler, f"History button {button_name}")

        search_input = history_page.findChild(QtWidgets.QLineEdit, "txtSearchRecord")
        subject_combo = history_page.findChild(QtWidgets.QComboBox, "cmbFilterSubject")
        sort_combo = history_page.findChild(QtWidgets.QComboBox, "cmbSortBy")
        date_from = history_page.findChild(QtWidgets.QDateEdit, "dateFromPicker")
        date_to = history_page.findChild(QtWidgets.QDateEdit, "dateToPicker")
        table = history_page.findChild(QtWidgets.QTableWidget, "tblStudyRecords")

        if search_input is not None:
            self._connect_safe(search_input.textChanged, self.load_history_data, "History filter")
        if subject_combo is not None:
            self._connect_safe(subject_combo.currentTextChanged, self.load_history_data, "History filter")
        if sort_combo is not None:
            self._connect_safe(sort_combo.currentTextChanged, self.load_history_data, "History filter")
        if date_from is not None:
            date_from.setCalendarPopup(False)
            date_from.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            date_from.setDisplayFormat("M/d/yyyy")
            date_from.setDate(QtCore.QDate.currentDate().addYears(-10))
            self._connect_safe(date_from.dateChanged, self.load_history_data, "History filter")
        if date_to is not None:
            date_to.setCalendarPopup(False)
            date_to.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            date_to.setDisplayFormat("M/d/yyyy")
            date_to.setDate(QtCore.QDate.currentDate())
            self._connect_safe(date_to.dateChanged, self.load_history_data, "History filter")

        if table is not None:
            
            table.setColumnCount(9)
            table.setHorizontalHeaderLabels(
                [
                    "Date",
                    "Subject",
                    "Content",
                    "Tag",
                    "Mood",
                    "Duration",
                    "Effectiveness",
                    "Note",
                    "ID",
                ]
            )
            header = table.horizontalHeader()
            if header is not None:
                header.setStretchLastSection(False)
                header.setSectionResizeMode(
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents
                )

            # Ẩn scrollbar nhưng vẫn cho phép scroll.
            table.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            table.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )

            table.setColumnHidden(8, True)
            table.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
            table.setWordWrap(False)
            table.setHorizontalScrollMode(
                QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
            )
            table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
            if header is not None:
                header.setStretchLastSection(False)
                header.setSectionResizeMode(
                    QtWidgets.QHeaderView.ResizeMode.ResizeToContents
                )
            table.setColumnHidden(8, True)
            table.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
            table.setWordWrap(False)
            table.setHorizontalScrollMode(
                QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
            )
            table.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
            self._connect_safe(
                table.itemSelectionChanged,
                self.update_history_preview,
                "History preview",
            )

    # Nạp dữ liệu bảng lịch sử học tập.
    def load_history_data(self):
        history_page = self._get_page_widget("history")
        if history_page is None:
            return

        table = history_page.findChild(QtWidgets.QTableWidget, "tblStudyRecords")
        if table is None:
            return

        if self.current_user is None:
            table.setRowCount(0)
            self.selected_history_record_id = None
            self.update_history_preview()
            return

        self.populate_history_subjects()

        search_input = history_page.findChild(QtWidgets.QLineEdit, "txtSearchRecord")
        subject_combo = history_page.findChild(QtWidgets.QComboBox, "cmbFilterSubject")
        sort_combo = history_page.findChild(QtWidgets.QComboBox, "cmbSortBy")
        date_from = history_page.findChild(QtWidgets.QDateEdit, "dateFromPicker")
        date_to = history_page.findChild(QtWidgets.QDateEdit, "dateToPicker")

        keyword = search_input.text().strip() if search_input is not None else ""
        subject = ""
        if subject_combo is not None:
            selected_subject = subject_combo.currentText().strip()
            if selected_subject.lower() != "all subjects":
                subject = selected_subject

        from_date = date_from.date().toString("yyyy-MM-dd") if date_from is not None else ""
        to_date = date_to.date().toString("yyyy-MM-dd") if date_to is not None else ""

        try:
            filtered_records = self.study_database.filter_records(
                username=self.current_user.username,
                keyword=keyword,
                subject=subject,
                from_date=from_date,
                to_date=to_date,
            )
        except ValueError as error:

            self._show_message("History", str(error), icon="warning")
            return

        sort_text = sort_combo.currentText().strip() if sort_combo is not None else ""
        sort_map = {

            "Newest first": ("date", True),
            "Oldest first": ("date", False),
            "Duration high": ("duration", True),
            "Effectiveness high": ("effectiveness", True),
        }
        sort_by, reverse = sort_map.get(sort_text, ("date", True))
        filtered_records = self.study_database.sort_records(
            filtered_records,
            sort_by=sort_by,
            reverse=reverse,
        )

        table.setRowCount(len(filtered_records))

        for row, record in enumerate(filtered_records):
            values = [
                record.date,
                record.subject,
                record.content,
                record.tag,
                record.mood,
                str(record.duration_minutes),
                str(record.effectiveness),
                record.note,
                str(record.id),
            ]

            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column == 8:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, record.id)
                table.setItem(row, column, item)

        table.resizeColumnsToContents()

        self._set_label_text(
            history_page,
            "lblRecordCount",
            f"Showing {len(filtered_records)} records",
        )
        self._set_label_text(
            history_page,
            "lblSidebarStatusValue",
            str(len(filtered_records)),
        )

        suggestions = InsightService.generate_suggestions(
            filtered_records,
            int(getattr(self.current_user, "goal_minutes_per_day", 120)),
        )
        self._set_label_text(
            history_page,
            "lblInsightBody",
            suggestions[0] if suggestions else "No suggestions yet.",
        )

        if filtered_records:
            table.selectRow(0)
            self.selected_history_record_id = filtered_records[0].id
        else:
            self.selected_history_record_id = None

        self.update_history_preview()

    # Nạp danh sách subject vào bộ lọc History.
    def populate_history_subjects(self):
        history_page = self._get_page_widget("history")
        if history_page is None or self.current_user is None:
            return

        subject_combo = history_page.findChild(QtWidgets.QComboBox, "cmbFilterSubject")
        if subject_combo is None:
            return

        current_text = subject_combo.currentText()
        subject_combo.blockSignals(True)
        subject_combo.clear()
        subject_combo.addItem("All subjects")
        for subject in self._get_subject_list_for_user():
            subject_combo.addItem(subject)

        index = subject_combo.findText(current_text)
        subject_combo.setCurrentIndex(index if index >= 0 else 0)
        subject_combo.blockSignals(False)

    # Khi chọn một dòng trong bảng, hiển thị chi tiết record ở panel preview.
    def update_history_preview(self):
        history_page = self._get_page_widget("history")
        if history_page is None:
            return

        table = history_page.findChild(QtWidgets.QTableWidget, "tblStudyRecords")
        record = None

        if table is not None and table.currentRow() >= 0:
            id_item = table.item(table.currentRow(), 8)
            if id_item is not None:
                record_id = id_item.data(QtCore.Qt.ItemDataRole.UserRole)
                self.selected_history_record_id = record_id
                if self.current_user is not None:
                    record = self.study_database.get_user_record_by_id(
                        self.current_user.username,
                        record_id,
                    )

        if record is None:
            self.selected_history_record_id = None
            self._set_label_text(history_page, "lblPreviewSubject", "Nothing selected")
            self._set_label_text(history_page, "lblPreviewMeta", "No record is currently selected.")
            self._set_label_text(history_page, "lblPreviewContent", "Select a record in the table to view its details.")
            self._set_label_text(history_page, "lblPreviewBadge", "View only")
            return

        self._set_label_text(history_page, "lblPreviewSubject", record.subject)
        self._set_label_text(
            history_page,
            "lblPreviewMeta",
            f"{record.date} • {record.duration_minutes} min • {record.mood or 'No mood'}",
        )
        self._set_label_text(history_page, "lblPreviewContent", record.content)
        self._set_label_text(history_page, "lblPreviewBadge", "View only")

    # Đưa bộ lọc History về mặc định và nạp lại dữ liệu.
    def clear_history_filters(self):
        history_page = self._get_page_widget("history")
        if history_page is None:
            return

        search_input = history_page.findChild(QtWidgets.QLineEdit, "txtSearchRecord")
        subject_combo = history_page.findChild(QtWidgets.QComboBox, "cmbFilterSubject")
        sort_combo = history_page.findChild(QtWidgets.QComboBox, "cmbSortBy")
        date_from = history_page.findChild(QtWidgets.QDateEdit, "dateFromPicker")
        date_to = history_page.findChild(QtWidgets.QDateEdit, "dateToPicker")

        if search_input is not None:
            search_input.clear()
        if subject_combo is not None:
            subject_combo.setCurrentIndex(0)
        if sort_combo is not None:
            sort_combo.setCurrentIndex(0)
        if date_from is not None:
            date_from.setDate(QtCore.QDate.currentDate().addYears(-10))
        if date_to is not None:
            date_to.setDate(QtCore.QDate.currentDate())

        self.load_history_data()

    # Mở record đang chọn trên History sang form CRUD để chỉnh sửa.
    def open_selected_record_for_edit(self):
        if self.current_user is None or self.selected_history_record_id is None:
            self._show_message("History", "Please select a record to edit.")
            return

        record = self.study_database.get_user_record_by_id(
            self.current_user.username,
            self.selected_history_record_id,
        )
        if record is None:
            self._show_message("History", "The selected record could not be found.", icon="warning")
            return

        self.current_record_id = record.id
        self.fill_crud_form_from_record(record)
        self.navigate("crud")

    # Xác nhận rồi xóa record đang chọn khỏi database.
    def delete_selected_history_record(self):
        if self.current_user is None or self.selected_history_record_id is None:
            self._show_message("History", "Please select a record to delete.")
            return

        record = self.study_database.get_user_record_by_id(
            self.current_user.username,
            self.selected_history_record_id,
        )
        if record is None:
            self._show_message("History", "The selected record could not be found.", icon="warning")
            return

        confirm = self._ask_confirmation(
            "Delete Record",
            "Are you sure you want to delete this record?",
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self.study_database.delete_record(record.id, username=self.current_user.username)
        self.selected_history_record_id = None
        self.load_dashboard_data()
        self.load_history_data()
        self.update_history_preview()
        self._show_message("History", "Record deleted.", icon="info")

    # ============================================================
    # STATISTICS
    # Thiết lập bộ lọc, chart, KPI card và insight cho màn thống kê.
    # ============================================================
    
    # Gắn action cho màn hình Statistics.
    def _setup_statistics_actions(self):
        statistics_page = self.pages.get("statistics")
        if statistics_page is None:
            return
        self._tune_statistics_chart_boxes(statistics_page)
        self._ensure_statistics_subject_widgets(statistics_page)
        self._configure_statistics_v1_insight(statistics_page)

        refresh_button = statistics_page.findChild(QtWidgets.QPushButton, "btnRefreshStats")
        export_button = statistics_page.findChild(QtWidgets.QPushButton, "btnExportStats")
        range_combo = statistics_page.findChild(QtWidgets.QComboBox, "cmbStatisticsRange")
        subject_combo = statistics_page.findChild(
            QtWidgets.QComboBox, "cmbStatisticsSubjectFilter"
        )

        if refresh_button is not None:
            self._connect_safe(refresh_button.clicked, self.load_statistics_data, "Refresh statistics")
        if export_button is not None:
            self._connect_safe(export_button.clicked, self.export_statistics_summary, "Export statistics")
        if range_combo is not None:
            custom_index = range_combo.findText("Custom")
            if custom_index >= 0:
                range_combo.removeItem(custom_index)
            self._connect_safe(range_combo.currentTextChanged, self.load_statistics_data, "Statistics filter")
        if subject_combo is not None:
            self._connect_safe(subject_combo.currentTextChanged, self.load_statistics_data, "Statistics filter")

        self._ensure_statistics_chart_widgets()

    # Thiết lập nội dung insight mặc định.
    def _configure_statistics_v1_insight(self, statistics_page):
        self._set_label_text(statistics_page, "lblInsightTitle", "Study insight")
        self._set_label_text(
            statistics_page,
            "lblInsightBody",
            "Insights in v1 are generated from your local study records.",
        )
        self._set_label_text(statistics_page, "lblBadgeLow", "Local analytics")

    # Bọc nội dung statistics vào scroll area để màn nhỏ vẫn xem đủ dữ liệu.
    def _ensure_statistics_scroll_area(self, statistics_page):
        if self.statistics_scroll_area is not None:
            return

        sidebar = statistics_page.findChild(QtWidgets.QFrame, "Sidebar")
        if sidebar is None:
            return

        viewport_width = 990
        viewport_height = max(560, statistics_page.height())
        sidebar_width = sidebar.geometry().width()

        self.statistics_scroll_area = QtWidgets.QScrollArea(statistics_page)
        self.statistics_scroll_area.setObjectName("statisticsScrollArea")
        self.statistics_scroll_area.setGeometry(sidebar_width, 0, viewport_width, viewport_height)
        self.statistics_scroll_area.setWidgetResizable(False)
        self.statistics_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.statistics_scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            """
        )

        self.statistics_scroll_content = QtWidgets.QWidget()
        self.statistics_scroll_content.setObjectName("statisticsScrollContent")
        self.statistics_scroll_content.setStyleSheet("background: transparent;")
        self.statistics_scroll_content.resize(viewport_width, 980)
        self.statistics_scroll_area.setWidget(self.statistics_scroll_content)

        content_widget_names = [
            "TopBar",
            "FilterCard",
            "KpiTotalCard",
            "KpiAvgCard",
            "KpiTopSubjectCard",
            "KpiGoalCard",
            "PieChartCard",
            "BarChartCard",
            "GoalTrackingCard",
            "InsightCard",
        ]

        for widget_name in content_widget_names:
            child = statistics_page.findChild(QtWidgets.QWidget, widget_name)
            if child is None:
                continue
            child_geometry = child.geometry()
            child.setParent(self.statistics_scroll_content)
            child.move(child_geometry.x() - sidebar_width, child_geometry.y())
            child.show()

    # Mở rộng kích thước các card statistics.
    def _expand_statistics_cards(self):
        statistics_page = self.pages.get("statistics")
        if statistics_page is None:
            return

        pie_card = statistics_page.findChild(QtWidgets.QFrame, "PieChartCard")
        pie_placeholder = statistics_page.findChild(QtWidgets.QFrame, "PiePlaceholder")
        pie_hint = statistics_page.findChild(QtWidgets.QLabel, "lblPieHint")
        pie_legends = [
            statistics_page.findChild(QtWidgets.QLabel, "lblLegendMath"),
            statistics_page.findChild(QtWidgets.QLabel, "lblLegendEnglish"),
            statistics_page.findChild(QtWidgets.QLabel, "lblLegendPhysics"),
        ]
        bar_card = statistics_page.findChild(QtWidgets.QFrame, "BarChartCard")
        bar_placeholder = statistics_page.findChild(QtWidgets.QFrame, "BarPlaceholder")
        bar_hint = statistics_page.findChild(QtWidgets.QLabel, "lblBarHint")
        goal_card = statistics_page.findChild(QtWidgets.QFrame, "GoalTrackingCard")
        insight_card = statistics_page.findChild(QtWidgets.QFrame, "InsightCard")

        if pie_card is not None:
            pie_card.setGeometry(0, 282, 430, 300)
        if pie_placeholder is not None:
            pie_placeholder.setGeometry(20, 48, 230, 220)
        if pie_hint is not None:
            pie_hint.setGeometry(268, 210, 130, 56)

        legend_positions = [
            (268, 62, 130, 24),
            (268, 98, 130, 24),
            (268, 134, 130, 24),
        ]
        for label, geometry in zip(pie_legends, legend_positions):
            if label is not None:
                label.setGeometry(*geometry)

        if bar_card is not None:
            bar_card.setGeometry(458, 282, 532, 300)
        if bar_placeholder is not None:
            bar_placeholder.setGeometry(20, 48, 492, 220)
        if bar_hint is not None:
            bar_hint.setGeometry(20, 272, 470, 20)

        if goal_card is not None:
            goal_card.setGeometry(0, 610, 430, 150)
        if insight_card is not None:
            insight_card.setGeometry(458, 610, 532, 150)

        if self.statistics_scroll_content is not None:
            self.statistics_scroll_content.resize(990, 800)

    # Điều chỉnh kích thước vùng biểu đồ statistics.
    def _tune_statistics_chart_boxes(self, statistics_page):
        pie_placeholder = statistics_page.findChild(QtWidgets.QFrame, "PiePlaceholder")
        bar_placeholder = statistics_page.findChild(QtWidgets.QFrame, "BarPlaceholder")

        if pie_placeholder is not None:
            pie_placeholder.setGeometry(20, 40, 176, 136)

        if bar_placeholder is not None:
            bar_placeholder.setGeometry(20, 40, 600, 130)

    # Tạo QChartView cho biểu đồ nếu máy có PyQt6-Charts.
    def _ensure_statistics_chart_widgets(self):
        statistics_page = self.pages.get("statistics")
        if statistics_page is None:
            return

        pie_placeholder = statistics_page.findChild(QtWidgets.QFrame, "PiePlaceholder")
        bar_placeholder = statistics_page.findChild(QtWidgets.QFrame, "BarPlaceholder")
        pie_label = statistics_page.findChild(QtWidgets.QLabel, "lblPiePlaceholderText")
        bar_label = statistics_page.findChild(QtWidgets.QLabel, "lblBarPlaceholderText")

        if QtCharts is None:
            if pie_label is not None:
                pie_label.setText("PyQt6-Charts is missing.")
            if bar_label is not None:
                bar_label.setText("PyQt6-Charts is missing.")
            return

        if (
            pie_placeholder is not None
            and self.statistics_pie_chart_view is None
        ):
            self.statistics_pie_chart_view = QtCharts.QChartView(pie_placeholder)
            self.statistics_pie_chart_view.setRenderHint(
                QtGui.QPainter.RenderHint.Antialiasing
            )
            self.statistics_pie_chart_view.setGeometry(pie_placeholder.rect())
            self.statistics_pie_chart_view.setStyleSheet(
                "background: transparent; border: none;"
            )
            if pie_label is not None:
                pie_label.hide()

        if (
            bar_placeholder is not None
            and self.statistics_bar_chart_view is None
        ):
            self.statistics_bar_chart_view = QtCharts.QChartView(bar_placeholder)
            self.statistics_bar_chart_view.setRenderHint(
                QtGui.QPainter.RenderHint.Antialiasing
            )
            self.statistics_bar_chart_view.setGeometry(bar_placeholder.rect())
            self.statistics_bar_chart_view.setStyleSheet(
                "background: transparent; border: none;"
            )
            if bar_label is not None:
                bar_label.hide()

    # Thay các legend/goal cố định bằng danh sách động theo subject của user.
    def _ensure_statistics_subject_widgets(self, statistics_page):
        pie_card = statistics_page.findChild(QtWidgets.QFrame, "PieChartCard")
        goal_card = statistics_page.findChild(QtWidgets.QFrame, "GoalTrackingCard")

        if pie_card is not None:
            pie_hint = pie_card.findChild(QtWidgets.QLabel, "lblPieHint")
            if pie_hint is not None:
                pie_hint.hide()

            for object_name in ("lblLegendMath", "lblLegendEnglish", "lblLegendPhysics"):
                label = pie_card.findChild(QtWidgets.QLabel, object_name)
                if label is not None:
                    label.hide()

            if self.statistics_legend_scroll_area is None:
                self.statistics_legend_scroll_area = QtWidgets.QScrollArea(pie_card)
                self.statistics_legend_scroll_area.setObjectName("statisticsLegendScrollArea")
                self.statistics_legend_scroll_area.setWidgetResizable(True)
                self.statistics_legend_scroll_area.setVerticalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
                )
                self.statistics_legend_scroll_area.setHorizontalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                self.statistics_legend_scroll_area.setStyleSheet(
                    """
                    QScrollArea {
                        background: transparent;
                        border: none;
                    }
                    QScrollArea > QWidget > QWidget {
                        background: transparent;
                    }
                    QScrollBar:vertical {
                        width: 0px;
                    }
                    QScrollBar:horizontal {
                        height: 0px;
                    }
                    """
                )
                self.statistics_legend_container = QtWidgets.QWidget()
                self.statistics_legend_layout = QtWidgets.QVBoxLayout(
                    self.statistics_legend_container
                )
                self.statistics_legend_layout.setContentsMargins(0, 0, 0, 0)
                self.statistics_legend_layout.setSpacing(8)
                self.statistics_legend_layout.setSizeConstraint(
                    QtWidgets.QLayout.SizeConstraint.SetMinAndMaxSize
                )
                self.statistics_legend_scroll_area.setWidget(self.statistics_legend_container)

            self.statistics_legend_scroll_area.setGeometry(210, 48, 170, 170)

        if goal_card is not None:
            for object_name in (
                "lblMathGoalText",
                "lblEnglishGoalText",
                "lblPhysicsGoalText",
            ):
                label = goal_card.findChild(QtWidgets.QLabel, object_name)
                if label is not None:
                    label.hide()

            for object_name in (
                "progressMathGoal",
                "progressEnglishGoal",
                "progressPhysicsGoal",
            ):
                progress = goal_card.findChild(QtWidgets.QProgressBar, object_name)
                if progress is not None:
                    progress.hide()

            if self.statistics_goal_scroll_area is None:
                self.statistics_goal_scroll_area = QtWidgets.QScrollArea(goal_card)
                self.statistics_goal_scroll_area.setObjectName("statisticsGoalScrollArea")
                self.statistics_goal_scroll_area.setWidgetResizable(True)
                self.statistics_goal_scroll_area.setVerticalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
                )
                self.statistics_goal_scroll_area.setHorizontalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                self.statistics_goal_scroll_area.setStyleSheet(
                    """
                    QScrollArea {
                        background: transparent;
                        border: none;
                    }
                    QScrollArea > QWidget > QWidget {
                        background: transparent;
                    }
                    QScrollBar:vertical {
                        width: 0px;
                    }
                    QScrollBar:horizontal {
                        height: 0px;
                    }
                    """
                )
                self.statistics_goal_container = QtWidgets.QWidget()
                self.statistics_goal_layout = QtWidgets.QVBoxLayout(
                    self.statistics_goal_container
                )
                self.statistics_goal_layout.setContentsMargins(0, 0, 0, 0)
                self.statistics_goal_layout.setSpacing(10)
                self.statistics_goal_layout.setSizeConstraint(
                    QtWidgets.QLayout.SizeConstraint.SetMinAndMaxSize
                )
                self.statistics_goal_scroll_area.setWidget(self.statistics_goal_container)

            self.statistics_goal_scroll_area.setGeometry(20, 42, 390, 106)

    # ============================================================
    # STATISTICS FILTERING
    # Nạp subject và lọc record theo subject/khoảng thời gian.
    # ============================================================
    def populate_statistics_subjects(self):
        statistics_page = self._get_page_widget("statistics")
        if statistics_page is None:
            return

        subject_combo = statistics_page.findChild(
            QtWidgets.QComboBox, "cmbStatisticsSubjectFilter"
        )
        if subject_combo is None:
            return

        current_text = subject_combo.currentText().strip()
        subject_combo.blockSignals(True)
        subject_combo.clear()
        subject_combo.addItem("All subjects")
        for subject in self._get_subject_list_for_user():
            subject_combo.addItem(subject)

        index = subject_combo.findText(current_text)
        subject_combo.setCurrentIndex(index if index >= 0 else 0)
        subject_combo.blockSignals(False)

    # Lọc record theo subject và khoảng thời gian đang chọn trên màn Statistics.
    def _get_statistics_filtered_records(self):
        if self.current_user is None:
            return [], []

        statistics_page = self._get_page_widget("statistics")
        if statistics_page is None:
            return [], []

        all_records = self.study_database.get_records_by_username(self.current_user.username)
        subject_combo = statistics_page.findChild(
            QtWidgets.QComboBox, "cmbStatisticsSubjectFilter"
        )
        range_combo = statistics_page.findChild(QtWidgets.QComboBox, "cmbStatisticsRange")

        subject_filter = ""
        if subject_combo is not None:
            selected_subject = subject_combo.currentText().strip()
            if selected_subject.lower() != "all subjects":
                subject_filter = selected_subject

        range_text = range_combo.currentText().strip() if range_combo is not None else "7 days"
        today_date = datetime.now().date()

        filtered_records = []

        for record in all_records:
            if subject_filter and record.subject.strip() != subject_filter:
                continue

            record_date = InsightService._parse_record_date(record.date)
            if record_date is None:
                continue

            include_record = True
            if range_text == "Today":
                include_record = record_date == today_date
            elif range_text == "7 days":
                include_record = today_date - timedelta(days=6) <= record_date <= today_date
            elif range_text == "30 days":
                include_record = today_date - timedelta(days=29) <= record_date <= today_date

            if include_record:
                filtered_records.append(record)

        return filtered_records, all_records

    # Tính toán KPI, biểu đồ và insight cho màn Statistics.
    def load_statistics_data(self):
        statistics_page = self.pages.get("statistics")
        if statistics_page is None:
            return

        if self.current_user is None:
            self._set_label_text(statistics_page, "lblSidebarStatusValue", "0")
            return

        self.populate_statistics_subjects()
        filtered_records, all_records = self._get_statistics_filtered_records()
        goal_minutes = int(getattr(self.current_user, "goal_minutes_per_day", 120))

        total_minutes = sum(record.duration_minutes for record in filtered_records)
        daily_totals = InsightService.get_daily_totals(filtered_records)
        average_minutes = round(sum(daily_totals.values()) / len(daily_totals), 1) if daily_totals else 0
        subject_distribution = InsightService.get_subject_distribution(filtered_records)
        top_subject = InsightService.get_top_subject(filtered_records) or "No data"
        top_subject_share = 0
        if top_subject != "No data":
            total_distribution = sum(subject_distribution.values())
            if total_distribution > 0:
                top_subject_share = round(
                    (subject_distribution.get(top_subject, 0) / total_distribution) * 100
                )

        goal_days = InsightService.count_goal_days_this_week(all_records, goal_minutes)
        goal_consistency = "Good consistency" if goal_days >= 5 else "Needs improvement"

        previous_minutes = self._get_previous_period_total_minutes(
            filtered_records,
            range_text=statistics_page.findChild(
                QtWidgets.QComboBox, "cmbStatisticsRange"
            ).currentText().strip()
            if statistics_page.findChild(QtWidgets.QComboBox, "cmbStatisticsRange") is not None
            else "7 days",
            subject_filter=statistics_page.findChild(
                QtWidgets.QComboBox, "cmbStatisticsSubjectFilter"
            ).currentText().strip()
            if statistics_page.findChild(
                QtWidgets.QComboBox, "cmbStatisticsSubjectFilter"
            ) is not None
            else "All subjects",
        )
        diff_minutes = total_minutes - previous_minutes
        diff_prefix = "+" if diff_minutes >= 0 else "-"

        self._set_label_text(statistics_page, "lblGreeting", "Study Statistics")
        self._set_label_text(
            statistics_page,
            "lblDateToday",
            "Analyze study time, subject balance, goals, and learning trends.",
        )
        self._set_label_text(statistics_page, "lblKpiTotalValue", self._format_minutes_short(total_minutes))
        self._set_label_text(
            statistics_page,
            "lblKpiTotalSub",
            f"{diff_prefix}{self._format_minutes_short(abs(diff_minutes))} vs previous period",
        )
        self._set_label_text(statistics_page, "lblKpiAvgValue", self._format_minutes_short(average_minutes))
        self._set_label_text(
            statistics_page,
            "lblKpiAvgSub",
            f"Goal: {self._format_minutes_short(goal_minutes)} / day",
        )
        self._set_label_text(statistics_page, "lblKpiTopSubjectValue", top_subject)
        self._set_label_text(
            statistics_page,
            "lblKpiTopSubjectSub",
            f"{top_subject_share}% of total time" if top_subject_share else "No data",
        )
        self._set_label_text(statistics_page, "lblKpiGoalValue", f"{goal_days} / 7")
        self._set_label_text(statistics_page, "lblKpiGoalSub", goal_consistency)
        self._set_label_text(statistics_page, "lblSidebarStatusValue", str(len(filtered_records)))
        self._set_label_text(
            statistics_page,
            "lblSidebarStatusSub",
            "Charts are generated from study_records.json.",
        )
        self._set_label_text(statistics_page, "lblBadgeGood", f"{goal_days}/7 goal days")
        self._set_label_text(
            statistics_page,
            "lblBadgeWarning",
            self._build_statistics_warning_badge(subject_distribution, goal_minutes),
        )
        self._set_label_text(statistics_page, "lblInsightTitle", "Study insight")
        self._set_label_text(
            statistics_page,
            "lblInsightBody",
            InsightService.generate_suggestions(filtered_records, goal_minutes)[0]
            if filtered_records
            else "No data for the current filter.",
        )
        self._set_label_text(
            statistics_page,
            "lblBadgeLow",
            "Local analytics" if filtered_records else "No data",
        )

        self._update_statistics_goal_tracking(statistics_page, filtered_records)
        self._update_statistics_legends(statistics_page, subject_distribution)
        self._render_statistics_pie_chart(subject_distribution)
        self._render_statistics_trend_chart(filtered_records)

    # Tính tổng phút học của giai đoạn trước để so sánh.
    def _get_previous_period_total_minutes(self, filtered_records, range_text: str, subject_filter: str):
        if self.current_user is None:
            return 0

        all_records = self.study_database.get_records_by_username(self.current_user.username)
        today_date = datetime.now().date()
        previous_records = []

        for record in all_records:
            if subject_filter and subject_filter.lower() != "all subjects":
                if record.subject.strip() != subject_filter:
                    continue

            record_date = InsightService._parse_record_date(record.date)
            if record_date is None:
                continue

            include_record = False
            if range_text == "Today":
                include_record = record_date == today_date - timedelta(days=1)
            elif range_text == "7 days":
                start = today_date - timedelta(days=13)
                end = today_date - timedelta(days=7)
                include_record = start <= record_date <= end
            elif range_text == "30 days":
                start = today_date - timedelta(days=59)
                end = today_date - timedelta(days=30)
                include_record = start <= record_date <= end

            if include_record:
                previous_records.append(record)

        return sum(record.duration_minutes for record in previous_records)

    # Tạo nội dung cảnh báo nhanh cho màn Statistics.
    def _build_statistics_warning_badge(self, subject_distribution: dict, goal_minutes: int):
        if not subject_distribution:
            return "No data"

        lowest_subject = min(subject_distribution, key=subject_distribution.get)
        subject_minutes = subject_distribution.get(lowest_subject, 0)
        delta = max(0, goal_minutes - subject_minutes)
        if delta <= 0:
            return f"{lowest_subject} on track"
        return f"{lowest_subject} low -{delta}m"

    # Lấy danh sách subject dùng để hiển thị slot thống kê.
    def _get_statistics_slot_subjects(self, subject_distribution: dict):
        subjects = []
        for subject in self._get_subject_list_for_user():
            self._append_unique_subject(subjects, subject)

        settings = self.user_manager.load_settings()
        subject_goals = settings.get("subject_goals", {})
        if isinstance(subject_goals, dict):
            for subject_name in subject_goals.keys():
                self._append_unique_subject(subjects, str(subject_name).strip())

        sorted_subjects = sorted(
            subject_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for subject_name, _minutes in sorted_subjects:
            self._append_unique_subject(subjects, subject_name)

        return subjects

    # Cập nhật phần chú thích subject trong biểu đồ tròn.
    def _update_statistics_legends(self, statistics_page, subject_distribution: dict):
        total_minutes = sum(subject_distribution.values())
        slot_subjects = self._get_statistics_slot_subjects(subject_distribution)

        if self.statistics_legend_layout is not None:
            self._clear_layout_widgets(self.statistics_legend_layout)

            if not slot_subjects or total_minutes <= 0:
                empty_label = QtWidgets.QLabel("No data", self.statistics_legend_container)
                empty_label.setStyleSheet("color:#6B7280; font-size:12px;")
                self.statistics_legend_layout.addWidget(empty_label)
                self.statistics_legend_layout.addStretch()
                return

            for subject_name in slot_subjects:
                minutes = subject_distribution.get(subject_name, 0)
                percent = round((minutes / total_minutes) * 100) if total_minutes > 0 else 0
                label = QtWidgets.QLabel(
                    f"{subject_name} {percent}%",
                    self.statistics_legend_container,
                )
                label.setStyleSheet("color:#6B7280; font-size:12px; font-weight:600;")
                self.statistics_legend_layout.addWidget(label)

            self.statistics_legend_layout.addStretch()
            self.statistics_legend_container.adjustSize()
            self.statistics_legend_container.updateGeometry()
            return

        legend_names = ["lblLegendMath", "lblLegendEnglish", "lblLegendPhysics"]
        for index, object_name in enumerate(legend_names):
            label = statistics_page.findChild(QtWidgets.QLabel, object_name)
            if label is None:
                continue

            if index < len(slot_subjects) and total_minutes > 0:
                subject_name = slot_subjects[index]
                minutes = subject_distribution.get(subject_name, 0)
                percent = round((minutes / total_minutes) * 100)
                label.setText(f"{subject_name} {percent}%")
                label.show()
            else:
                label.setText("No data")
                label.hide()

    # Cập nhật tiến độ mục tiêu học theo từng subject.
    def _update_statistics_goal_tracking(self, statistics_page, filtered_records):
        settings = self.user_manager.load_settings()
        subject_goals = settings.get("subject_goals", {})
        subject_totals = InsightService.get_subject_distribution(filtered_records)
        subjects = self._get_statistics_slot_subjects(subject_totals)

        if self.statistics_goal_layout is not None:
            self._clear_layout_widgets(self.statistics_goal_layout)

            if not subjects:
                empty_label = QtWidgets.QLabel("No data", self.statistics_goal_container)
                empty_label.setStyleSheet("color:#6B7280; font-size:12px;")
                self.statistics_goal_layout.addWidget(empty_label)
                return

            for subject_name in subjects:
                goal_value = max(1, int(subject_goals.get(subject_name, 120)))
                current_value = int(subject_totals.get(subject_name, 0))
                percent = min(100, round((current_value / goal_value) * 100))

                row_widget = QtWidgets.QWidget(self.statistics_goal_container)
                row_widget.setMinimumHeight(28)
                row_layout = QtWidgets.QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(10)

                label = QtWidgets.QLabel(f"{subject_name} {percent}%", row_widget)
                label.setMinimumWidth(120)
                label.setStyleSheet("color:#6B7280; font-size:12px;")

                progress = QtWidgets.QProgressBar(row_widget)
                progress.setRange(0, 100)
                progress.setValue(percent)
                progress.setTextVisible(True)
                progress.setFormat(f"{percent}%")

                row_layout.addWidget(label)
                row_layout.addWidget(progress, 1)
                self.statistics_goal_layout.addWidget(row_widget)

            self.statistics_goal_container.adjustSize()
            self.statistics_goal_container.updateGeometry()
            return

        slots = [
            ("lblMathGoalText", "progressMathGoal"),
            ("lblEnglishGoalText", "progressEnglishGoal"),
            ("lblPhysicsGoalText", "progressPhysicsGoal"),
        ]

        for index, (label_name, progress_name) in enumerate(slots):
            label = statistics_page.findChild(QtWidgets.QLabel, label_name)
            progress = statistics_page.findChild(QtWidgets.QProgressBar, progress_name)
            if label is None or progress is None:
                continue

            if index < len(subjects):
                subject_name = subjects[index]
                goal_value = max(1, int(subject_goals.get(subject_name, 120)))
                current_value = int(subject_totals.get(subject_name, 0))
                percent = min(100, round((current_value / goal_value) * 100))
                label.setText(f"{subject_name} {percent}%")
                progress.setValue(percent)
                progress.show()
            else:
                label.setText("No data")
                progress.setValue(0)

    # Vẽ biểu đồ tròn phân bổ thời gian học theo subject.
    def _render_statistics_pie_chart(self, subject_distribution: dict):
        if QtCharts is None or self.statistics_pie_chart_view is None:
            return

        chart = QtCharts.QChart()
        chart.setBackgroundVisible(False)
        chart.legend().hide()
        chart.setMargins(QtCore.QMargins(0, 0, 0, 0))

        series = QtCharts.QPieSeries()
        colors = ["#FF6B6B", "#F97316", "#10B981", "#3B82F6", "#8B5CF6"]

        if not subject_distribution:
            slice_item = series.append("No data", 1)
            slice_item.setColor(QtGui.QColor("#E5E7EB"))
        else:
            sorted_subjects = sorted(
                subject_distribution.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            for index, (subject_name, minutes) in enumerate(sorted_subjects):
                slice_item = series.append(subject_name, minutes)
                slice_item.setColor(QtGui.QColor(colors[index % len(colors)]))
                slice_item.setLabelVisible(False)

        chart.addSeries(series)
        self.statistics_pie_chart_view.setChart(chart)

    # Vẽ biểu đồ xu hướng học tập theo ngày.
    def _render_statistics_trend_chart(self, filtered_records):
        if QtCharts is None or self.statistics_bar_chart_view is None:
            return

        trend_items = InsightService.get_daily_trend(filtered_records, days=7)
        chart = QtCharts.QChart()
        chart.setBackgroundVisible(False)
        chart.setMargins(QtCore.QMargins(28, 8, 12, 8))

        line_series = QtCharts.QLineSeries()
        line_series.setName("Study time")
        line_series.setColor(QtGui.QColor("#F97316"))
        line_series.setPen(QtGui.QPen(QtGui.QColor("#F97316"), 3))
        line_series.setPointsVisible(True)
        line_series.setPointLabelsVisible(True)
        line_series.setPointLabelsFormat("@yPoint min")
        line_series.setPointLabelsClipping(False)
        line_series.setPointLabelsColor(QtGui.QColor("#C2410C"))
        line_series.setPointLabelsFont(QtGui.QFont("Segoe UI", 9))
        categories = []

        for index, item in enumerate(trend_items):
            minutes = int(item.get("minutes", 0))
            line_series.append(index, minutes)
            categories.append(item.get("date", "")[5:])

        chart.addSeries(line_series)

        axis_x = QtCharts.QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-20)
        chart.addAxis(axis_x, QtCore.Qt.AlignmentFlag.AlignBottom)
        line_series.attachAxis(axis_x)

        axis_y = QtCharts.QValueAxis()
        max_minutes = max([int(item.get("minutes", 0)) for item in trend_items] + [30])
        axis_y.setRange(0, max_minutes + 10)
        axis_y.setLabelFormat("%d")
        axis_y.setTickCount(5)
        axis_y.setMinorTickCount(0)
        axis_y.setLabelsVisible(False)
        chart.addAxis(axis_y, QtCore.Qt.AlignmentFlag.AlignLeft)
        line_series.attachAxis(axis_y)

        chart.legend().hide()
        chart.layout().setContentsMargins(0, 0, 0, 0)
        self.statistics_bar_chart_view.setChart(chart)

    # Xuất nhanh tóm tắt thống kê hiện tại ra file JSON.
    def export_statistics_summary(self):
        if self.current_user is None:
            return

        filtered_records, _all_records = self._get_statistics_filtered_records()
        subject_distribution = InsightService.get_subject_distribution(filtered_records)
        trend_items = InsightService.get_daily_trend(filtered_records, days=7)
        payload = {
            "username": self.current_user.username,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_records": len(filtered_records),
            "total_minutes": sum(record.duration_minutes for record in filtered_records),
            "subject_distribution": subject_distribution,
            "trend": trend_items,
        }

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Statistics",
            str(BASE_DIR / "statistics_summary.json"),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        data_io.write_json(Path(file_path), payload)
        self._show_message("Statistics", "Statistics were exported to a JSON file.", icon="info")

    # ============================================================
    # PROFILE
    # Quản lý thông tin user, mục tiêu học tập, import/export và reset dữ liệu.
    # ============================================================
    def _setup_profile_actions(self):
        profile_page = self.pages.get("profile")
        if profile_page is None:
            return

        self._ensure_profile_subject_widgets(profile_page)

        # objectName của nút -> hàm xử lý tương ứng.
        action_map = {
            "btnSaveProfile": self.save_profile_display_name,
            "btnSaveGoals": self.save_profile_goals,
            "btnSavePreferences": self.save_profile_preferences,
            "btnLogout": self.logout_current_user,
            "btnResetData": self.reset_current_user_data,
            "btnExportData": self.export_study_data,
            "btnImportData": self.import_study_data,
            "btnAddSubject": self.add_profile_subject,
            "btnDeleteSubject": self.delete_profile_subject,
        }

        for button_name, handler in action_map.items():
            button = profile_page.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(button.clicked, handler, f"Profile button {button_name}")

    # Dựng khu vực nhập mục tiêu theo từng subject bằng scroll area động.
    def _ensure_profile_subject_widgets(self, profile_page):
        subject_card = profile_page.findChild(QtWidgets.QFrame, "SubjectGoalCard")
        if subject_card is None:
            return

        subject_card.setGeometry(260, 290, 430, 160)

        hint_label = profile_page.findChild(QtWidgets.QLabel, "lblSubjectGoalHint")
        if hint_label is not None:
            hint_label.setGeometry(24, 122, 360, 24)

        add_button = profile_page.findChild(QtWidgets.QPushButton, "btnAddSubject")
        if add_button is not None:
            add_button.setGeometry(280, 80, 141, 31)

        delete_button = profile_page.findChild(QtWidgets.QPushButton, "btnDeleteSubject")
        if delete_button is None:
            delete_button = QtWidgets.QPushButton(subject_card)
            delete_button.setObjectName("btnDeleteSubject")
            delete_button.setText("- Delete Subject")
            delete_button.setStyleSheet(
                """
                QPushButton {
                    background: #FFF7F7;
                    color: #FF6B6B;
                    border: 1px solid #FFC2C2;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: #FFECEC;
                }
                """
            )
        delete_button.setGeometry(280, 40, 141, 31)

        static_names = [
            "lblMathGoal",
            "txtMathGoal",
            "lblMathUnit",
            "lblEnglishGoal",
            "txtEnglishGoal",
            "lblEnglishUnit",
            "lblPhysicsGoal",
            "txtPhysicsGoal",
            "lblPhysicsUnit",
        ]
        for object_name in static_names:
            widget = subject_card.findChild(QtWidgets.QWidget, object_name)
            if widget is not None:
                widget.hide()

        if self.profile_subject_scroll_area is None:
            self.profile_subject_scroll_area = QtWidgets.QScrollArea(subject_card)
            self.profile_subject_scroll_area.setObjectName("profileSubjectScrollArea")
            self.profile_subject_scroll_area.setGeometry(10, 40, 410, 72)
            self.profile_subject_scroll_area.setWidgetResizable(True)
            self.profile_subject_scroll_area.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.profile_subject_scroll_area.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.profile_subject_scroll_area.setStyleSheet(
                """
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background: transparent;
                }
                QScrollBar:vertical {
                    width: 0px;
                }
                QScrollBar:horizontal {
                    height: 0px;
                }
                """
            )

            self.profile_subject_container = QtWidgets.QWidget()
            self.profile_subject_form_layout = QtWidgets.QFormLayout(self.profile_subject_container)
            self.profile_subject_form_layout.setContentsMargins(0, 0, 0, 0)
            self.profile_subject_form_layout.setHorizontalSpacing(10)
            self.profile_subject_form_layout.setVerticalSpacing(8)
            self.profile_subject_scroll_area.setWidget(self.profile_subject_container)

        self.profile_subject_scroll_area.setGeometry(10, 40, 410, 72)
        if add_button is not None:
            add_button.raise_()
        if delete_button is not None:
            delete_button.raise_()
        if hint_label is not None:
            hint_label.raise_()

    # Tạo lại từng dòng subject + ô nhập goal từ danh sách subject hiện có.
    def _rebuild_profile_subject_rows(self, profile_page, subject_goals: dict):
        if self.profile_subject_form_layout is None:
            return

        # self.profile_subject_form_layout là layout động nên cần dọn dòng cũ trước khi dựng lại.
        while self.profile_subject_form_layout.rowCount() > 0:
            self.profile_subject_form_layout.removeRow(0)

        # self.profile_subject_goal_inputs lưu ô nhập theo subject để lúc Save đọc lại nhanh.
        self.profile_subject_goal_inputs = {}
        subjects = self._get_subject_list_for_user()

        for subject_name in subjects:
            label = QtWidgets.QLabel(subject_name, self.profile_subject_container)
            label.setStyleSheet("color:#374151; font-size:12px; font-weight:700;")

            row_widget = QtWidgets.QWidget(self.profile_subject_container)
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            field = QtWidgets.QLineEdit(row_widget)
            field.setPlaceholderText("Enter minutes")
            field.setText(str(subject_goals.get(subject_name, 120)))
            field.setFixedSize(120, 30)

            unit = QtWidgets.QLabel("min/week", row_widget)
            unit.setStyleSheet("color:#6B7280; font-size:12px;")
            unit.setFixedWidth(70)

            row_layout.addWidget(field)
            row_layout.addWidget(unit)
            row_layout.addStretch()

            self.profile_subject_form_layout.addRow(label, row_widget)
            self.profile_subject_goal_inputs[subject_name] = field

    # Nạp thông tin user, setting và subject goals lên màn Profile.
    def load_profile_data(self):
        profile_page = self.pages.get("profile")
        if profile_page is None or self.current_user is None:
            return

        settings = self.user_manager.load_settings()
        username = self._get_current_user_label()
        created_at = getattr(self.current_user, "created_at", "")
        created_text = "Unknown"

        if created_at:
            try:
                created_text = datetime.fromisoformat(created_at).strftime("%d/%m/%Y")
            except ValueError:
                created_text = created_at

        self._set_label_text(profile_page, "lblProfileName", username)
        self._set_label_text(profile_page, "lblProfileMeta", f"Joined on: {created_text}")
        self._set_label_text(profile_page, "lblSidebarStatusValue", username)
        self._set_label_text(
            profile_page,
            "lblSidebarStatusSub",
            "Goals and settings are saved in settings.json.",
        )

        display_input = profile_page.findChild(QtWidgets.QLineEdit, "txtDisplayName")
        if display_input is not None:
            display_input.setText(username)

        daily_goal_spin = profile_page.findChild(QtWidgets.QSpinBox, "spinDailyGoalMinutes")
        if daily_goal_spin is not None:
            daily_goal_spin.setValue(int(getattr(self.current_user, "goal_minutes_per_day", 120)))

        default_session_spin = profile_page.findChild(QtWidgets.QSpinBox, "spinDefaultSessionLength")
        if default_session_spin is not None:
            default_session_spin.setValue(int(settings.get("default_session_length", 45)))

        theme_combo = profile_page.findChild(QtWidgets.QComboBox, "cmbThemeMode")
        if theme_combo is not None:
            index = theme_combo.findText(settings.get("theme", "Light"))
            theme_combo.setCurrentIndex(index if index >= 0 else 0)

        reminder_check = profile_page.findChild(QtWidgets.QCheckBox, "chkNotification")
        if reminder_check is not None:
            reminder_check.setChecked(bool(settings.get("reminder_enabled", True)))

        subject_goals = settings.get("subject_goals", {})
        self._rebuild_profile_subject_rows(profile_page, subject_goals)
        shown_subject_count = len(self.profile_subject_goal_inputs)

        self._set_label_text(
            profile_page,
            "lblGoalBadge",
            f"{shown_subject_count} subjects shown",
        )

    # Lưu tên hiển thị mới cho user hiện tại.
    def save_profile_display_name(self):
        if self.current_user is None:
            return

        profile_page = self.pages.get("profile")
        if profile_page is None:
            return

        display_input = profile_page.findChild(QtWidgets.QLineEdit, "txtDisplayName")
        new_username = display_input.text().strip() if display_input is not None else ""
        old_username = self.current_user.username

        if new_username == old_username:
            self._show_message("Profile", "Username is unchanged.", icon="info")
            return

        try:
            self.study_database.rename_records_username(
                old_username,
                new_username,
            )
            self.current_user = self.user_manager.update_display_name(
                old_username,
                new_username,
            )
        except ValueError as error:
            self._show_message("Profile", str(error), icon="warning")
            return
        except Exception as error:
            try:
                self.study_database.rename_records_username(new_username, old_username)
            except Exception:
                pass
            self._show_message("Profile", f"Could not update username: {error}", icon="warning")
            return

        self.load_profile_data()
        self.load_dashboard_header()
        self.load_dashboard_data()
        self.load_history_data()
        self._show_message("Profile", "Username updated.", icon="info")

    # Lưu mục tiêu học tập chung và mục tiêu theo từng subject.
    def save_profile_goals(self):
        if self.current_user is None:
            return

        profile_page = self.pages.get("profile")
        if profile_page is None:
            return

        daily_goal_spin = profile_page.findChild(QtWidgets.QSpinBox, "spinDailyGoalMinutes")
        default_session_spin = profile_page.findChild(QtWidgets.QSpinBox, "spinDefaultSessionLength")

        daily_goal = daily_goal_spin.value() if daily_goal_spin is not None else 120
        default_session = default_session_spin.value() if default_session_spin is not None else 45

        try:
            self.user_manager.update_goal_minutes(
                self.current_user.username,
                daily_goal,
            )
        except ValueError as error:
            self._show_message("Goals", str(error), icon="warning")
            return

        self.user_manager.update_settings({"default_session_length": default_session})
        self.user_manager.load_users()
        self.current_user = self.user_manager.get_user_by_username(
            self.current_user.username,
            include_inactive=False,
        )
        self.load_profile_data()
        self._show_message("Goals", "Study goals saved.", icon="info")

    # Lưu tùy chọn giao diện/thông báo của user.
    def save_profile_preferences(self):
        profile_page = self.pages.get("profile")
        if profile_page is None:
            return

        theme_combo = profile_page.findChild(QtWidgets.QComboBox, "cmbThemeMode")
        reminder_check = profile_page.findChild(QtWidgets.QCheckBox, "chkNotification")

        # Chuyển dữ liệu goal nhập từ UI thành số phút hợp lệ.
        def parse_goal(field, default_value):
            text = field.text().strip() if field is not None else ""
            if not text:
                return default_value
            return max(0, int(text))

        settings = self.user_manager.load_settings()
        subject_goals = dict(settings.get("subject_goals", {}))

        try:
            for subject_name, field in self.profile_subject_goal_inputs.items():
                subject_goals[subject_name] = parse_goal(
                    field,
                    int(subject_goals.get(subject_name, 120)),
                )
        except ValueError:
            self._show_message("Preferences", "Subject goals must be whole numbers.", icon="warning")
            return

        theme_value = theme_combo.currentText().strip() if theme_combo is not None else "Light"
        reminder_value = reminder_check.isChecked() if reminder_check is not None else True

        self.user_manager.update_settings(
            {
                "theme": theme_value,
                "reminder_enabled": reminder_value,
                "subject_goals": subject_goals,
            }
        )
        self.populate_crud_subjects()
        self.populate_session_subjects()
        self.load_profile_data()
        self._show_message("Preferences", "Preferences and subject goals saved.", icon="info")

    # Thêm subject mới vào setting và cập nhật lại các combo liên quan.
    def add_profile_subject(self):
        if self.current_user is None:
            self._show_message("Add Subject", "You need to log in first.", icon="warning")
            return

        subject_name, ok = self._prompt_text(
            "Add Subject",
            "Enter a new subject name:",
        )
        if not ok:
            return

        subject_name = subject_name.strip()
        if not subject_name:
            self._show_message("Add Subject", "Subject name cannot be empty.", icon="warning")
            return

        settings = self.user_manager.load_settings()
        subject_goals = dict(settings.get("subject_goals", {}))
        hidden_subjects = [
            subject for subject in settings.get("hidden_subjects", [])
            if str(subject).strip().lower() != subject_name.lower()
        ]

        if subject_name.lower() in {
            str(existing_subject).strip().lower() for existing_subject in subject_goals
        }:
            self._show_message("Add Subject", "This subject already exists.", icon="warning")
            return

        goal_minutes, ok = self._prompt_int(
            "Subject Goal",
            f"Weekly minute goal for {subject_name}:",
            120,
            0,
            5000,
            10,
        )
        if not ok:
            return

        existing_subject_key = next(
            (
                existing_subject
                for existing_subject in subject_goals
                if str(existing_subject).strip().lower() == subject_name.lower()
            ),
            subject_name,
        )
        subject_goals[existing_subject_key] = goal_minutes
        self.user_manager.update_settings(
            {
                "subject_goals": subject_goals,
                "hidden_subjects": hidden_subjects,
            }
        )

        self.populate_crud_subjects()
        self.populate_session_subjects()
        self.populate_history_subjects()
        self.populate_statistics_subjects()
        self.load_statistics_data()
        self.load_profile_data()
        self._show_message("Add Subject", "New subject added.", icon="info")

    # Ẩn subject khỏi UI sau khi user xác nhận.
    def delete_profile_subject(self):
        if self.current_user is None:
            self._show_message("Delete Subject", "You need to log in first.", icon="warning")
            return

        available_subjects = list(self.profile_subject_goal_inputs.keys())
        if not available_subjects:
            self._show_message("Delete Subject", "There are no subjects to delete yet.", icon="warning")
            return

        subject_name, ok = self._prompt_item(
            "Delete Subject",
            "Choose a subject to delete:",
            available_subjects,
            0,
        )
        if not ok or not subject_name:
            return

        subject_name = subject_name.strip()
        confirm = self._ask_confirmation(
            "Delete Subject",
            f"Are you sure you want to hide {subject_name} from the list?",
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        settings = self.user_manager.load_settings()
        subject_goals = dict(settings.get("subject_goals", {}))
        hidden_subjects = self._get_hidden_subjects()

        matched_subject_key = next(
            (
                existing_subject
                for existing_subject in subject_goals
                if str(existing_subject).strip().lower() == subject_name.lower()
            ),
            subject_name,
        )
        subject_goals.pop(matched_subject_key, None)
        if subject_name.lower() not in {subject.lower() for subject in hidden_subjects}:
            hidden_subjects.append(subject_name)

        self.user_manager.update_settings(
            {
                "subject_goals": subject_goals,
                "hidden_subjects": hidden_subjects,
            }
        )

        self.populate_crud_subjects()
        self.populate_session_subjects()
        self.populate_history_subjects()
        self.populate_statistics_subjects()
        self.load_statistics_data()
        self.load_profile_data()
        self._show_message("Delete Subject", "Subject removed from the visible list.", icon="info")

    # Đăng xuất user hiện tại và quay về màn Login.
    def logout_current_user(self):
        if self.current_user is None:
            self.navigate("login")
            return

        self.user_manager.logout_user(clear_remembered=True)
        self.current_user = None
        self.reset_session_state()
        self.current_record_id = None
        self.selected_history_record_id = None
        self.navigate("login")

    # Xóa toàn bộ dữ liệu học tập của user hiện tại sau khi xác nhận.
    def reset_current_user_data(self):
        if self.current_user is None:
            return

        self.study_database.delete_records_by_username(self.current_user.username)
        self.reset_session_state()
        self.reset_crud_form()
        self.load_dashboard_data()
        self.load_history_data()
        self._show_message("Reset Data", "Study data for the current account has been deleted.", icon="info")

    # Xuất toàn bộ dữ liệu học tập của user ra file JSON.
    def export_study_data(self):
        if self.current_user is None:
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Study Data",
            str(BASE_DIR / "study_records_export.json"),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        records = self.study_database.get_records_by_username(self.current_user.username)
        data_io.write_json(Path(file_path), [record.to_dict() for record in records])
        self._show_message("Export", "Study records exported to a JSON file.", icon="info")

    # Nhập dữ liệu học tập từ file JSON và refresh các màn liên quan.
    def import_study_data(self):
        if self.current_user is None:
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Study Data",
            str(BASE_DIR),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        imported_records = data_io.load_json(Path(file_path), [])
        if not isinstance(imported_records, list):
            self._show_message("Import", "The JSON file is invalid.", icon="warning")
            return

        imported_count = 0
        for item in imported_records:
            if not isinstance(item, dict):
                continue
            try:
                self.study_database.add_record(self.current_user.username, item)
                imported_count += 1
            except ValueError:
                continue

        self.populate_crud_subjects()
        self.populate_session_subjects()
        self.load_dashboard_data()
        self.load_history_data()
        self._show_message("Import", f"Imported {imported_count} record(s).", icon="info")

    # Load toàn bộ file .ui, lấy widget trung tâm và đưa vào QStackedWidget.
    def _load_pages(self):
        for route, ui_file in self.page_order.items():
            try:
                page_window = QtWidgets.QMainWindow()
                uic.loadUi(str(BASE_DIR / ui_file), page_window)
                self._normalize_invalid_fonts(page_window)
                page_widget = page_window.takeCentralWidget()
                if page_widget is None:
                    raise RuntimeError(f"{ui_file} has no central widget.")
            except Exception as error:
                page_window, page_widget = self._build_fallback_page(route, ui_file, error)
            self.page_windows[route] = page_window
            self.pages[route] = page_widget
            self.page_stack.addWidget(page_widget)
            self._bind_sidebar_navigation(page_widget)

    # Tạo page tạm nếu file .ui lỗi, giúp app vẫn mở được để báo lỗi rõ ràng.
    def _build_fallback_page(self, route: str, ui_file: str, error: Exception):
        page_window = QtWidgets.QMainWindow()
        page_window.setWindowTitle(f"Study Track - {route.title()} unavailable")
        placeholder = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(placeholder)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QtWidgets.QLabel(f"{route.title()} page could not be loaded.")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #1F2933;")
        body = QtWidgets.QLabel(f"UI file: {ui_file}\n{error}")
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 13px; color: #6B7280;")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch()
        page_window.setCentralWidget(placeholder)
        self._handle_runtime_error(f"Load page {route}", error)
        return page_window, placeholder

    # Sửa font size không hợp lệ trong file .ui để tránh cảnh báo QFont và vỡ giao diện.
    def _normalize_invalid_fonts(self, root_widget: QtWidgets.QWidget):
        widgets = [root_widget, *root_widget.findChildren(QtWidgets.QWidget)]
        for widget in widgets:
            font = widget.font()
            if font.pointSize() > 0:
                continue
            font.setPointSize(12)
            widget.setFont(font)

    # Gắn các nút sidebar với route tương ứng để chuyển màn hình.
    def _bind_sidebar_navigation(self, page_widget: QtWidgets.QWidget):
        # objectName của nút trong Qt Designer -> route cần mở.
        nav_buttons = {
            "BtnDashboard": "dashboard",
            "BtnSession": "session",
            "BtnHistory": "history",
            "BtnEditRecord": "crud",
            "BtnStats": "statistics",
            "BtnProfile": "profile",
        }

        for button_name, target_route in nav_buttons.items():
            button = page_widget.findChild(QtWidgets.QPushButton, button_name)
            if button is not None:
                self._connect_safe(
                    button.clicked,
                    self._make_navigation_handler(target_route),
                    f"Sidebar button {button_name}",
                )

    # Tạo handler riêng cho từng nút điều hướng, tránh lambda khó debug.
    def _make_navigation_handler(self, route: str):
        # Thực hiện điều hướng đến route đã được truyền vào.
        def handler(_checked=False):
            self.navigate(route)

        return handler

    # Chuyển màn hình theo route và nạp dữ liệu cần thiết trước khi hiển thị.
    # Các màn cần đăng nhập sẽ tự đẩy về login nếu chưa có current_user.
    def navigate(self, route: str):
        page_widget = self.pages.get(route)
        page_window = self.page_windows.get(route)
        if page_widget is None or page_window is None:
            return

        protected_routes = {"dashboard", "session", "history", "crud", "statistics", "profile"}
        if route in protected_routes and self.current_user is None:
            route = "login"
            page_widget = self.pages.get(route)
            page_window = self.page_windows.get(route)
            if page_widget is None or page_window is None:
                return

        if route == self.current_route:
            return

        try:
            if route == "dashboard":
                self.load_dashboard_header()
                self.load_dashboard_data()

            if route == "session":
                self.load_session_page()

            if route == "crud":
                self.populate_crud_subjects()
                self.update_crud_preview()

            if route == "history":
                self.load_history_data()

            if route == "statistics":
                self.load_statistics_data()

            if route == "profile":
                self.load_profile_data()

            self.setUpdatesEnabled(False)
            self.setStyleSheet(page_window.styleSheet())
            self.setWindowTitle(page_window.windowTitle())
            self.setMinimumSize(page_window.minimumSize())
            self.resize(page_window.size())
            self.page_stack.setCurrentWidget(page_widget)
            self.current_route = route
        except Exception as error:
            self._handle_runtime_error(f"Navigate to {route}", error)
        finally:
            self.setUpdatesEnabled(True)

    # Gán text cho QLabel nếu widget tồn tại.
    def _set_label_text(self, page_window, object_name: str, text: str):
        label = page_window.findChild(QtWidgets.QLabel, object_name)
        if label is not None:
            label.setText(text)

    # Lấy widget page theo route.
    def _get_page_widget(self, route: str):
        return self.pages.get(route)

    # Lấy tên hiển thị của user hiện tại.
    def _get_current_user_label(self):
        if self.current_user is None:
            return "Guest"
        return self.current_user.username

    # Đổi số phút thành dạng ngắn để hiển thị trên dashboard, ví dụ 90 -> 1h 30m.
    def _format_minutes_short(self, minutes):
        total_minutes = int(round(minutes or 0))
        hours = total_minutes // 60
        remain_minutes = total_minutes % 60

        if hours > 0:
            return f"{hours}h {remain_minutes:02d}m"
        return f"{remain_minutes}m"

    # Đổi số giây thành đồng hồ HH:MM:SS cho phiên học.
    def _format_session_clock(self, total_seconds):
        total_seconds = max(0, int(total_seconds or 0))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Làm tròn thời lượng học lên phút, tối thiểu 1 phút nếu đã có phiên học.
    def _normalize_session_duration_minutes(self, total_seconds):
        total_seconds = max(0, int(total_seconds or 0))
        if total_seconds == 0:
            return 1
        return (total_seconds + 59) // 60

    # In traceback ra terminal và phát signal để hiện popup lỗi cho người dùng.
    def _handle_runtime_error(self, context: str, error: Exception):
        traceback.print_exc()
        try:
            self.runtime_error_signal.emit("Application Error", f"{context}: {error}")
        except Exception:
            pass

    # Hiển thị popup lỗi runtime cho người dùng.
    def _show_runtime_error_message(self, title: str, text: str):
        self._show_message(title, text, icon="soft_warning")

    # Chạy từng bước khởi động riêng lẻ để dễ khoanh vùng lỗi startup.
    def _run_startup_step(self, label: str, action):
        try:
            action()
        except Exception as error:
            self._handle_runtime_error(label, error)

    # Bắt lỗi chưa xử lý ở main thread và thread phụ, rồi đưa về popup chung.
    def _install_global_exception_hooks(self):
        # Bắt lỗi runtime chưa được xử lý trong main thread.
        def runtime_exception_hook(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                _handle_keyboard_interrupt(exc_type, exc_value, exc_traceback)
                return
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            try:
                self.runtime_error_signal.emit(
                    "Unhandled Error",
                    f"{exc_type.__name__}: {exc_value}",
                )
            except Exception:
                pass

        sys.excepthook = runtime_exception_hook

        if hasattr(threading, "excepthook"):
            # Bắt lỗi runtime chưa được xử lý trong thread phụ.
            def thread_exception_hook(args):
                runtime_exception_hook(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                )

            threading.excepthook = thread_exception_hook

    # Tạo wrapper an toàn cho mọi callback PyQt, tránh crash khi handler lỗi.
    def _make_safe_handler(self, handler, context: str):
        try:
            signature = inspect.signature(handler)
            parameter_count = len(
                [
                    parameter
                    for parameter in signature.parameters.values()
                    if parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                ]
            )
            has_varargs = any(
                parameter.kind == inspect.Parameter.VAR_POSITIONAL
                for parameter in signature.parameters.values()
            )
        except (TypeError, ValueError):
            parameter_count = 0
            has_varargs = True

        # Bọc hàm gốc để bắt lỗi và truyền đúng tham số cần thiết.
        def wrapped(*args, **kwargs):
            try:
                if has_varargs:
                    return handler(*args, **kwargs)
                return handler(*args[:parameter_count])
            except Exception as error:
                self._handle_runtime_error(context, error)
                return None

        return wrapped

    # Bọc signal handler để lỗi trong nút bấm không làm crash toàn app.
    # Phần này cũng tự cắt số tham số cho khớp với handler.
    def _connect_safe(self, signal, handler, context: str):
        signal.connect(self._make_safe_handler(handler, context))

    # Popup thông báo dùng chung cho toàn app, mở non-modal để không khóa giao diện.
    def _show_message(self, title: str, text: str, icon: str = "warning"):
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        message_box.setModal(False)

        if icon == "info":
            message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        else:
            message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)

        message_box.setStyleSheet(self._dialog_stylesheet())
        self._open_message_boxes.append(message_box)
        message_box.finished.connect(
            lambda _result, box=message_box: self._dismiss_message_box(box)
        )
        message_box.open()

    # Đóng popup sau một khoảng thời gian nếu còn tồn tại.
    def _dismiss_message_box(self, message_box: QtWidgets.QMessageBox):
        if message_box in self._open_message_boxes:
            self._open_message_boxes.remove(message_box)
        message_box.deleteLater()

    # Style chung cho QMessageBox và QInputDialog để popup đồng bộ giao diện.
    def _dialog_stylesheet(self):
        return """
            QMessageBox, QInputDialog {
                background-color: #FFFFFF;
            }
            QMessageBox QLabel, QInputDialog QLabel {
                color: #1F2933;
                font-size: 13px;
            }
            QMessageBox QPushButton, QInputDialog QPushButton {
                background-color: #FF6B6B;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
                background-color: #E85A5A;
            }
            QInputDialog QLineEdit, QInputDialog QComboBox, QInputDialog QSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #FFD0D0;
                border-radius: 12px;
                padding: 8px 10px;
                color: #1F2933;
                min-height: 22px;
            }
            QInputDialog QLineEdit:focus, QInputDialog QComboBox:focus, QInputDialog QSpinBox:focus {
                border: 1px solid #FF6B6B;
            }
        """

    # Áp dụng style cho input dialog.
    def _style_input_dialog(self, dialog: QtWidgets.QInputDialog):
        dialog.setStyleSheet(self._dialog_stylesheet())
        dialog.setModal(True)
        return dialog

    # Popup Yes/No cho thao tác cần xác nhận như xóa hoặc reset dữ liệu.
    def _ask_confirmation(self, title: str, text: str):
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        message_box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        message_box.setStyleSheet(self._dialog_stylesheet())
        return message_box.exec()

    # Popup nhập một chuỗi ngắn, dùng cho các tác vụ cấu hình nhanh.
    def _prompt_text(self, title: str, label: str):
        dialog = self._style_input_dialog(QtWidgets.QInputDialog(self))
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QtWidgets.QInputDialog.InputMode.TextInput)
        accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    # Popup chọn một giá trị từ danh sách có sẵn.
    def _prompt_item(self, title: str, label: str, items, current: int = 0):
        dialog = self._style_input_dialog(QtWidgets.QInputDialog(self))
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QtWidgets.QInputDialog.InputMode.TextInput)
        dialog.setComboBoxItems(list(items))
        dialog.setComboBoxEditable(False)
        dialog.setTextValue(list(items)[current] if items else "")
        accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    # Popup nhập số nguyên có giới hạn min/max và bước nhảy.
    def _prompt_int(
        self,
        title: str,
        label: str,
        value: int,
        minimum: int,
        maximum: int,
        step: int,
    ):

        dialog = self._style_input_dialog(QtWidgets.QInputDialog(self))
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setInputMode(QtWidgets.QInputDialog.InputMode.IntInput)
        dialog.setIntRange(minimum, maximum)
        dialog.setIntStep(step)
        dialog.setIntValue(value)
        accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
        return dialog.intValue(), accepted

    # Xóa toàn bộ widget con trong layout trước khi dựng lại danh sách động.
    def _clear_layout_widgets(self, layout):
        if layout is None:
            return

        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout_widgets(child_layout)

    # ============================================================
    # SUBJECT COLLECTION
    # Gom subject từ setting, database và UI, đồng thời loại trùng/ẩn.
    # ============================================================
    def _append_unique_subject(self, subject_list, subject_name):
        subject_name = (subject_name or "").strip()
        if not subject_name:
            return
        if subject_name.lower() not in {item.lower() for item in subject_list}:
            subject_list.append(subject_name)

    # Lấy danh sách subject đang bị ẩn trong settings.
    def _get_hidden_subjects(self):
        settings = self.user_manager.load_settings()
        hidden_subjects = settings.get("hidden_subjects", [])
        if not isinstance(hidden_subjects, list):
            return []
        return [str(subject).strip() for subject in hidden_subjects if str(subject).strip()]

    # Quét các combobox trên nhiều màn để thu subject đang có trên UI.
    def _get_subject_list_from_ui_sources(self):
        subjects = []
        hidden_subjects = {subject.lower() for subject in self._get_hidden_subjects()}
        placeholder_values = {
            "all subjects",
            "chua co",
            "chua chon",
        }
        combo_targets = [
            ("session", "cmbSessionSubject"),
            ("crud", "cmbSubject"),
            ("history", "cmbFilterSubject"),
            ("statistics", "cmbStatisticsSubjectFilter"),
        ]

        for route, object_name in combo_targets:
            page = self._get_page_widget(route)
            if page is None:
                continue

            combo = page.findChild(QtWidgets.QComboBox, object_name)
            if combo is None:
                continue

            for index in range(combo.count()):
                subject_name = combo.itemText(index).strip()
                if subject_name.lower() in placeholder_values or subject_name.lower() in hidden_subjects:
                    continue
                self._append_unique_subject(subjects, subject_name)

        return subjects

    # Trả danh sách subject cuối cùng cho user hiện tại, ưu tiên setting và database.
    def _get_subject_list_for_user(self):
        subjects = []
        hidden_subjects = {subject.lower() for subject in self._get_hidden_subjects()}

        try:
            settings = self.user_manager.load_settings()
            subject_goals = settings.get("subject_goals", {})
            if isinstance(subject_goals, dict):
                for subject in subject_goals.keys():
                    if str(subject).strip().lower() not in hidden_subjects:
                        self._append_unique_subject(subjects, subject)
        except Exception:
            pass

        if self.current_user is not None:
            try:
                for subject in self.study_database.get_subject_list(self.current_user.username):
                    if str(subject).strip().lower() not in hidden_subjects:
                        self._append_unique_subject(subjects, subject)
            except Exception:
                pass

        for subject in self._get_subject_list_from_ui_sources():
            if subject.lower() not in hidden_subjects:
                self._append_unique_subject(subjects, subject)

        return subjects

# ============================================================
# APP ENTRY POINT
# Tạo QApplication, mở MainWindow và bắt đầu vòng lặp giao diện.
# ============================================================
def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Xử lý tín hiệu Ctrl+C để thoát app an toàn.
    def _handle_sigint(_signal_number, _frame):
        window.close()
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
