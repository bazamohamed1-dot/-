from django.db import models

class ClassShortcut(models.Model):
    """
    Stores the full class name and its standardized short format for use in checkboxes and charts.
    Example: full_name="أولى 1", shortcut="1م1"
    """
    full_name = models.CharField(max_length=50, unique=True, verbose_name="الاسم الكامل للقسم")
    shortcut = models.CharField(max_length=20, unique=True, verbose_name="اختصار القسم")

    class Meta:
        verbose_name = "اختصار القسم"
        verbose_name_plural = "اختصارات الأقسام"

    def __str__(self):
        return f"{self.full_name} ({self.shortcut})"

def ensure_class_shortcuts_populated():
    """
    Scans the Student table for distinct academic_year and class_name combinations
    and ensures a ClassShortcut exists for them.
    This guarantees the system consistently uses formats like 1م1 instead of "أولى 1"
    for checkboxes and charts.
    """
    from .models import Student
    db_combinations = Student.objects.exclude(academic_year__isnull=True).exclude(academic_year='')\
                                     .exclude(class_name__isnull=True).exclude(class_name='')\
                                     .values_list('academic_year', 'class_name').distinct()

    arabic_level_map = {
        'أولى': '1', 'الاولى': '1', 'الأولى': '1', 'اولى': '1',
        'ثانية': '2', 'الثانية': '2', 'ثانيه': '2', 'الثانيه': '2',
        'ثالثة': '3', 'الثالثة': '3', 'ثالثه': '3', 'الثالثه': '3',
        'رابعة': '4', 'الرابعة': '4', 'رابعه': '4', 'الرابعه': '4',
        # Handle cases where level is just '1', '2'
        '1': '1', '2': '2', '3': '3', '4': '4'
    }

    for level, cl_name in db_combinations:
        full = f"{level} {cl_name}".strip()
        if not full:
            continue

        # Check if already exists
        if ClassShortcut.objects.filter(full_name=full).exists():
            continue

        # Determine the shortcut
        level_str = level.strip()
        mapped_digit = None

        # 1. Try mapping the first word or the whole level string
        for arb_word, digit in arabic_level_map.items():
            if level_str.startswith(arb_word):
                mapped_digit = digit
                break

        # 2. Try the first character if it's a digit
        if not mapped_digit and level_str and level_str[0].isdigit():
            mapped_digit = level_str[0]

        shortcut_val = full  # Fallback
        if mapped_digit:
            # We assume "م" for "متوسط" (Middle School). This is the standard in Algeria.
            shortcut_val = f"{mapped_digit}م{cl_name}"

        # Create it safely
        try:
            ClassShortcut.objects.create(full_name=full, shortcut=shortcut_val)
        except Exception:
            pass # Ignore unique constraint violations if they occur concurrently

class ClassAlias(models.Model):
    """
    Maps various class name formats (e.g., "1M1", "1 م 1") to the canonical database level and class number.
    """
    alias = models.CharField(max_length=50, unique=True, verbose_name="الاسم المستعار (من الملف)")
    canonical_level = models.CharField(max_length=50, verbose_name="المستوى الموافق (في القاعدة)", default="")
    canonical_class = models.CharField(max_length=50, verbose_name="القسم الموافق (في القاعدة)")

    class Meta:
        verbose_name = "تعيين اسم القسم"
        verbose_name_plural = "تعيينات أسماء الأقسام"

    def __str__(self):
        return f"{self.alias} -> {self.canonical_level} {self.canonical_class}"

class TeacherAlias(models.Model):
    """
    Maps a teacher's name found in an imported file to the actual Employee (teacher) in the database.
    """
    alias_name = models.CharField(max_length=150, unique=True, verbose_name="الاسم المستعار (من الملف)")
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='aliases', verbose_name="الأستاذ الموافق (في القاعدة)")

    class Meta:
        verbose_name = "تعيين اسم الأستاذ"
        verbose_name_plural = "تعيينات أسماء الأساتذة"

    def __str__(self):
        return f"{self.alias_name} -> {self.employee.full_name}"
