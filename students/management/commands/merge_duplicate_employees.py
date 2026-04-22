"""
دمج الموظفين المكررين حسب تطابق الاسم (اللقب والاسم) مع تطبيع الحروف العربية.
يحتفظ بالسجل الأكثر اكتمالاً (الذي له رمز وظيفي ورتبة) ويحذف المكررات.
"""
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from students.models import Employee, TeacherAssignment


def norm(s):
    """تطبيع الأسماء العربية لاستيعاب الاختلافات الإملائية الشائعة."""
    if not s:
        return ''
    s = str(s).strip()
    s = s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    s = s.replace('ة', 'ه').replace('ى', 'ي')
    s = s.replace('ئ', 'ي').replace('ؤ', 'و').replace('ء', '')  # فائزة=فايزة
    s = re.sub(r'(^|\s)اع', r'\1ع', s)  # بن اعمارة=بن عمارة
    return s


class Command(BaseCommand):
    help = 'دمج الموظفين المكررين حسب الاسم (اللقب + الاسم)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='عرض التكرارات دون الحذف')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('وضع التجربة: لن يتم حذف أو دمج أي سجل'))

        all_emps = list(Employee.objects.all().order_by('id'))
        groups = {}

        for emp in all_emps:
            ln = norm(emp.last_name or '')
            fn = norm(emp.first_name or '')
            if not ln and not fn:
                continue
            key = (ln, fn)
            if key not in groups:
                groups[key] = []
            groups[key].append(emp)

        merge_pairs = []
        for key, emps in groups.items():
            if len(emps) < 2:
                continue
            def score(e):
                s = 0
                if e.employee_code and len(str(e.employee_code)) > 5:
                    s += 2
                if e.rank and e.rank != 'admin':
                    s += 1
                if e.subject and e.subject not in ('', '/'):
                    s += 1
                return (-s, e.id)
            emps.sort(key=score)
            keeper = emps[0]
            for dup in emps[1:]:
                merge_pairs.append((keeper, dup))

        if not merge_pairs:
            self.stdout.write(self.style.SUCCESS('لا توجد تكرارات.'))
            return

        self.stdout.write(f'عدد التكرارات للدمج: {len(merge_pairs)}')
        for keeper, dup in merge_pairs:
            self.stdout.write(f'  دمج: حذف id={dup.id} ({dup.last_name} {dup.first_name}) -> الإبقاء على id={keeper.id}')

        if not dry_run and merge_pairs:
            with transaction.atomic():
                for keeper, dup in merge_pairs:
                    for ta in TeacherAssignment.objects.filter(teacher=dup):
                        if not TeacherAssignment.objects.filter(teacher=keeper, subject=ta.subject).exists():
                            TeacherAssignment.objects.create(
                                teacher=keeper, subject=ta.subject, classes=ta.classes or []
                            )
                    if dup.analytics_assignments:
                        keeper_list = list(keeper.analytics_assignments or [])
                        keeper_subjs = {a.get('subject', '').strip() for a in keeper_list}
                        for a in (dup.analytics_assignments or []):
                            subj = (a.get('subject') or '').strip()
                            if subj and subj not in keeper_subjs:
                                keeper_list.append(a)
                                keeper_subjs.add(subj)
                        keeper.analytics_assignments = keeper_list
                        keeper.save(update_fields=['analytics_assignments'])
                    dup.delete()
            self.stdout.write(self.style.SUCCESS('تم دمج وحذف المكررات.'))
        elif dry_run:
            self.stdout.write(self.style.WARNING('لم يتم الحذف (وضع التجربة).'))
