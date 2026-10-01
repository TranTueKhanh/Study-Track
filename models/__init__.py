# ============================================================
# FILE: models/__init__.py
# Export nhanh các model/service chính của package `models`.
# Giúp import gọn hơn và nhìn rõ public API của package.
# ============================================================


# ============================================================
# ENTITY EXPORTS
# Các object dữ liệu chính của ứng dụng.
# ============================================================

from .entities import StudyRecord, User


# ============================================================
# SERVICE EXPORTS
# Các service xử lý logic nghiệp vụ của app.
# ============================================================

from .insight_service import InsightService

from .study_database import StudyDatabase

from .user_manager import UserManager


# ============================================================
# PUBLIC API
# Danh sách object được phép export khi import *
# ============================================================

__all__ = [
    "InsightService",
    "StudyDatabase",
    "StudyRecord",
    "User",
    "UserManager",
]