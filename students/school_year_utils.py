# -*- coding: utf-8 -*-
"""
مرجع السنة الدراسية من إعدادات المؤسسة.
السنة الحالية = من واجهة الإعدادات (SchoolSettings.academic_year).
"""
import re


def _parse_year_pair(s):
    """استخراج (y1, y2) من صيغة 'YYYY-YYYY' أو 'YYYY/YYYY'."""
    if not s or not isinstance(s, str):
        return None, None
    s = str(s).strip()
    m = re.match(r'^(\d{4})[-/](\d{4})$', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _format_year(y1, y2):
    return f"{y1}-{y2}"


def get_current_school_year():
    """
    السنة الحالية من إعدادات المؤسسة.
    إن لم تُحدَّد، تُرجع 2025-2026 كقيمة احتياطية.
    """
    from .models import SchoolSettings
    settings = SchoolSettings.objects.first()
    if settings and settings.academic_year:
        return str(settings.academic_year).strip()
    return "2025-2026"


def get_prev_school_year(current=None):
    """
    السنة الماضية (الحالية - 1).
    مثال: 2025-2026 -> 2024-2025
    """
    current = current or get_current_school_year()
    y1, y2 = _parse_year_pair(current)
    if y1 is not None and y2 is not None:
        return _format_year(y1 - 1, y2 - 1)
    return "2024-2025"


def get_school_year_before_prev(current=None):
    """
    السنة التي قبل الماضية (الحالية - 2).
    مثال: 2025-2026 -> 2023-2024
    """
    current = current or get_current_school_year()
    y1, y2 = _parse_year_pair(current)
    if y1 is not None and y2 is not None:
        return _format_year(y1 - 2, y2 - 2)
    return "2023-2024"


def get_school_year_info():
    """
    يرجع: (current_year, prev_year, year_before_prev)
    """
    current = get_current_school_year()
    return current, get_prev_school_year(current), get_school_year_before_prev(current)
