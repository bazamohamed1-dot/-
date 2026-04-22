"""
إصلاح خلط الإسناد بين طرافي امباركة وأرفيس امباركة (نفس اللقب، اسم مختلف):
- طرافي امباركة: لغة عربية + تربية إسلامية فقط (إزالة الرياضيات)
- أرفيس امباركة: الرياضيات فقط (استعادة الأقسام من طرافي)

يعتمد على اللقب والاسم معاً لتمييز الأستاذتين.
"""
from django.core.management.base import BaseCommand
from students.models import Employee, TeacherAssignment


class Command(BaseCommand):
    help = 'إصلاح خلط إسناد طرافي امباركة (عربية/إسلامية) وأرفيس امباركة (رياضيات)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='عرض التغييرات دون الحفظ')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('وضع التجربة: لن يتم حفظ أي تغيير'))

        teachers = list(Employee.objects.filter(rank='teacher'))
        tarafi = None  # طرافي امباركة — لغة عربية وتربية إسلامية
        arfis = None   # أرفيس امباركة — رياضيات

        for t in teachers:
            ln = (t.last_name or '').strip()
            fn = (t.first_name or '').strip()
            if 'امباركة' in ln or 'إمباركة' in ln or 'مباركة' in ln or 'امباركه' in ln:
                if 'طرافي' in fn or 'طرافى' in fn:
                    tarafi = t
                if 'أرفيس' in fn or 'ارفيس' in fn or 'ارفيس' in fn:
                    arfis = t

        if not tarafi:
            self.stdout.write(self.style.ERROR('لم يتم العثور على "طرافي امباركة" (الاسم يحتوي طرافي واللقب امباركة)'))
            self._list_teachers(teachers)
            return
        if not arfis:
            self.stdout.write(self.style.ERROR('لم يتم العثور على "أرفيس امباركة" (الاسم يحتوي أرفيس واللقب امباركة)'))
            self._list_teachers(teachers)
            return

        self.stdout.write(f'طرافي امباركة: id={tarafi.id}')
        self.stdout.write(f'أرفيس امباركة: id={arfis.id}')

        math_keys = ['الرياضيات', 'رياضيات', 'رياضيه']
        arabic_keys = ['لغة عربية', 'لغة عرب', 'عربي']
        islamic_keys = ['تربية إسلامية', 'تربيه اسلام', 'إسلامية']

        # 1) استخراج الرياضيات وأقسامها من طرافي (لنقلها لأرفيس)
        tarafi_ta = list(TeacherAssignment.objects.filter(teacher=tarafi))
        math_assignment = None
        tarafi_new_ta = []

        for ta in tarafi_ta:
            subj = (ta.subject or '').strip()
            if any(k in subj for k in math_keys):
                math_assignment = {'subject': 'الرياضيات', 'classes': list(ta.classes or [])}
                continue
            tarafi_new_ta.append(ta)

        # 2) تحديث طرافي: حذف الرياضيات، الإبقاء على عربية وإسلامية فقط
        if not dry_run:
            TeacherAssignment.objects.filter(teacher=tarafi).delete()
            for ta in tarafi_new_ta:
                TeacherAssignment.objects.create(teacher=tarafi, subject=ta.subject, classes=ta.classes or [])
            if not tarafi_new_ta:
                TeacherAssignment.objects.create(teacher=tarafi, subject='لغة عربية', classes=[])
                TeacherAssignment.objects.create(teacher=tarafi, subject='التربية الإسلامية', classes=[])

        # 3) أرفيس امباركة: إضافة الرياضيات بالأقسام المنقولة
        if math_assignment and math_assignment.get('classes'):
            if not dry_run:
                TeacherAssignment.objects.filter(teacher=arfis).delete()
                TeacherAssignment.objects.create(
                    teacher=arfis,
                    subject='الرياضيات',
                    classes=math_assignment['classes']
                )
            self.stdout.write(self.style.SUCCESS(f'نقل الرياضيات وأقسامها من طرافي إلى أرفيس امباركة: {math_assignment["classes"]}'))
        elif math_assignment:
            if not dry_run:
                existing = list(TeacherAssignment.objects.filter(teacher=arfis))
                has_math = any(any(m in (a.subject or '') for m in math_keys) for a in existing)
                if not has_math:
                    TeacherAssignment.objects.create(teacher=arfis, subject='الرياضيات', classes=[])

        if not dry_run:
            for emp in [tarafi, arfis]:
                tas = TeacherAssignment.objects.filter(teacher=emp)
                emp.analytics_assignments = [{'subject': ta.subject, 'classes': list(ta.classes or [])} for ta in tas]
                emp.save(update_fields=['analytics_assignments'])
            self.stdout.write(self.style.SUCCESS('تم حفظ التعديلات ومزامنة إسناد التحليل.'))
        else:
            self.stdout.write(self.style.WARNING('لم يتم الحفظ (وضع التجربة). شغّل بدون --dry-run للتطبيق.'))

    def _list_teachers(self, teachers):
        self.stdout.write('أساتذة اللقب امباركة:')
        for t in teachers:
            ln, fn = (t.last_name or '').strip(), (t.first_name or '').strip()
            if 'امباركة' in ln or 'مباركة' in ln:
                self.stdout.write(f'  id={t.id} | اللقب={ln} | الاسم={fn}')
