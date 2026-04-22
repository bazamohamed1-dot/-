# -*- coding: utf-8 -*-
"""
أدوات استيراد وتحليل ملفات السنوات السابقة لتحليل خبراء التربية.
المطابقة المتقدمة: اللقب، الاسم، تاريخ الميلاد، الجنس (بدون المستوى ولا القسم).
"""
import re
from datetime import datetime


def normalize_arabic(text):
    """توحيد النص العربي للتطابق المرن."""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub("[أإآ]", "ا", text)
    text = re.sub("ة", "ه", text)
    text = re.sub("ى", "ي", text)
    text = re.sub("[\u064B-\u065F]", "", text)  # إزالة التشكيل
    return text


def normalize_name_part(val):
    """تنظيف جزء من الاسم للمقارنة."""
    if not val:
        return ""
    v = str(val).strip()
    v = re.sub(r'\s+', ' ', v)
    return v


def parse_date(val):
    """تحويل النص إلى تاريخ."""
    if not val:
        return None
    val = str(val).strip()
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
        try:
            dt = datetime.strptime(val, fmt)
            return dt.date() if hasattr(dt, 'date') else dt
        except (ValueError, TypeError):
            pass
    return None


def normalize_gender(val):
    """توحيد الجنس."""
    if not val:
        return None
    v = str(val).strip().lower()
    if v in ('ذكر', 'ذ', 'm', 'male', '1'): return 'ذكر'
    if v in ('أنثى', 'ء', 'انثى', 'f', 'female', '2'): return 'أنثى'
    return None


def _names_match(ln1, fn1, ln2, fn2):
    """مقارنة مرنة بين اسمين (لقب + اسم)."""
    ln1 = normalize_name_part(ln1)
    fn1 = normalize_name_part(fn1)
    ln2 = normalize_name_part(ln2)
    fn2 = normalize_name_part(fn2)
    if not ln1 and not fn1:
        return False
    # تطابق مباشر
    if ln1 == ln2 and fn1 == fn2:
        return True
    # تطابق معكوس (الاسم قبل اللقب)
    if ln1 == fn2 and fn1 == ln2:
        return True
    # تطابق مع التطبيع العربي
    n_ln1 = normalize_arabic(ln1)
    n_fn1 = normalize_arabic(fn1)
    n_ln2 = normalize_arabic(ln2)
    n_fn2 = normalize_arabic(fn2)
    if n_ln1 == n_ln2 and n_fn1 == n_fn2:
        return True
    if n_ln1 == n_fn2 and n_fn1 == n_ln2:
        return True
    # تطابق جزئي: الاسم الكامل (لقب اسم) يطابق
    full1 = f"{ln1} {fn1}".strip()
    full2 = f"{ln2} {fn2}".strip()
    full1_rev = f"{fn1} {ln1}".strip()
    if full1 == full2 or full1_rev == full2:
        return True
    n_full1 = normalize_arabic(full1)
    n_full2 = normalize_arabic(full2)
    if n_full1 == n_full2:
        return True
    # احتواء: أحد الاسمين داخل الآخر (للتعامل مع الاختلافات الطفيفة)
    if n_full1 and n_full2 and (n_full1 in n_full2 or n_full2 in n_full1):
        if len(n_full1) >= 4 and len(n_full2) >= 4:  # تجنب التطابق الخاطئ للأسماء القصيرة
            return True
    return False


def find_student_advanced(candidates, last_name, first_name, date_of_birth=None, gender=None):
    """
    البحث عن التلميذ في قائمة المرشحين باستخدام المطابقة المتقدمة.
    المرشحون = تلاميذ لديهم علامات في السنة الحالية (من لوحة تحليل النتائج).
    المعايير: اللقب، الاسم، تاريخ الميلاد، الجنس (عند التوفر).
    يتجاهل المستوى والقسم.

    :param candidates: قائمة/QuerySet من كائنات Student
    :param last_name: اللقب من الملف
    :param first_name: الاسم من الملف
    :param date_of_birth: تاريخ الميلاد (اختياري)
    :param gender: الجنس (اختياري)
    :return: Student أو None
    """
    if not last_name and not first_name:
        return None

    # تحويل إلى قائمة إن كان QuerySet
    cand_list = list(candidates) if hasattr(candidates, '__iter__') and not isinstance(candidates, (list, tuple)) else candidates

    # فلترة أولية بالجنس وتاريخ الميلاد إن وُجدا
    filtered = []
    for s in cand_list:
        if not _names_match(last_name, first_name, getattr(s, 'last_name', ''), getattr(s, 'first_name', '')):
            continue
        # التحقق من تاريخ الميلاد
        if date_of_birth:
            sdob = getattr(s, 'date_of_birth', None)
            if sdob and date_of_birth != sdob:
                continue
        # التحقق من الجنس
        if gender:
            sgender = getattr(s, 'gender', None)
            if sgender and gender != sgender:
                continue
        filtered.append(s)

    if len(filtered) == 1:
        return filtered[0]
    if len(filtered) > 1:
        # إن وُجد عدة مطابقات، نفضل من لديه تطابق أقوى (تاريخ ميلاد + جنس)
        for s in filtered:
            if date_of_birth and gender:
                if getattr(s, 'date_of_birth', None) == date_of_birth and getattr(s, 'gender', None) == gender:
                    return s
            if date_of_birth and getattr(s, 'date_of_birth', None) == date_of_birth:
                return s
            if gender and getattr(s, 'gender', None) == gender:
                return s
        return filtered[0]  # أي مطابقة

    # إن لم نجد بعد الفلترة، نبحث بدون dob/gender (مطابقة اسمية فقط)
    for s in cand_list:
        if _names_match(last_name, first_name, getattr(s, 'last_name', ''), getattr(s, 'first_name', '')):
            return s
    return None
