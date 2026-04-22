"""
إصلاح خلط الإسناد بين أرفيس شفية وأرفيس امباركة:
- أرفيس شفية: التربية الإسلامية + اللغة العربية
- أرفيس امباركة: الرياضيات فقط

ينقل الرياضيات وأقسامها من شفية إلى امباركة، ويضبط إسناد شفية.
"""
from django.core.management.base import BaseCommand
from students.models import Employee, TeacherAssignment


class Command(BaseCommand):
    help = 'إصلاح خلط إسناد أرفيس شفية وأرفيس امباركة'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='عرض التغييرات دون الحفظ',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('وضع التجربة: لن يتم حفظ أي تغيير'))

        teachers = Employee.objects.filter(rank='teacher')
        shafia = None
        imbaraka = None

        for t in teachers:
            ln = (t.last_name or '').strip()
            fn = (t.first_name or '').strip()
            full = f"{ln} {fn}".strip()
            if 'شفية' in ln or 'شفيه' in ln or 'شافية' in full:
                shafia = t
            if 'امباركة' in ln or 'إمباركة' in ln or 'مباركة' in ln or 'امباركه' in ln:
                imbaraka = t

        if not shafia:
            self.stdout.write(self.style.ERROR('لم يتم العثور على أستاذة "أرفيس شفية" (ابحث عن شفية في اللقب)'))
            self._list_teachers(teachers)
            return
        if not imbaraka:
            self.stdout.write(self.style.ERROR('لم يتم العثور على أستاذة "أرفيس امباركة" (ابحث عن امباركة في اللقب)'))
            self._list_teachers(teachers)
            return

        self.stdout.write(f'شفية: {shafia.last_name} {shafia.first_name} (id={shafia.id})')
        self.stdout.write(f'امباركة: {imbaraka.last_name} {imbaraka.first_name} (id={imbaraka.id})')

        # 1. استخراج الرياضيات من شفية
        math_subject_keys = ['الرياضيات', 'رياضيات', 'رياضيه']
        math_assignment = None
        shafia_analytics = list(shafia.analytics_assignments or [])

        for a in shafia_analytics:
            subj = (a.get('subject') or '').strip()
            if any(k in subj for k in math_subject_keys):
                math_assignment = {'subject': 'الرياضيات', 'classes': list(a.get('classes') or [])}
                break

        # 2. تحديث analytics_assignments لشفية: إزالة الرياضيات، إضافة التربية الإسلامية واللغة العربية
        new_shafia = []
        for a in shafia_analytics:
            subj = (a.get('subject') or '').strip()
            if any(k in subj for k in math_subject_keys):
                continue  # حذف الرياضيات
            if subj or (a.get('classes')):
                new_shafia.append(a)

        # إضافة التربية الإسلامية واللغة العربية إن لم تكونا موجودتين
        has_islamic = any('إسلام' in (a.get('subject') or '') or 'تربيه اسلام' in (a.get('subject') or '').lower() for a in new_shafia)
        has_arabic = any('عربي' in (a.get('subject') or '') or 'لغة عرب' in (a.get('subject') or '').lower() for a in new_shafia)

        if not has_islamic:
            new_shafia.append({'subject': 'التربية الإسلامية', 'classes': []})
        if not has_arabic:
            new_shafia.append({'subject': 'اللغة العربية', 'classes': []})

        # 3. تحديث analytics_assignments لامباركة: إضافة الرياضيات فقط
        imbaraka_analytics = list(imbaraka.analytics_assignments or [])
        # إزالة الرياضيات القديمة (ربما فارغة) وأي إسنادات فارغة
        imbaraka_analytics = [
            a for a in imbaraka_analytics
            if not any(k in (a.get('subject') or '') for k in math_subject_keys)
            and ((a.get('subject') or '').strip() or (a.get('classes')))
        ]

        if math_assignment and math_assignment.get('classes'):
            # إضافة الرياضيات بالأقسام المنقولة من شفية
            imbaraka_analytics.append(math_assignment)
        elif math_assignment:
            imbaraka_analytics.append({'subject': 'الرياضيات', 'classes': []})

        # عرض التغييرات
        self.stdout.write('')
        self.stdout.write('--- التغييرات المخططة ---')
        self.stdout.write(f'شفية (قبل): {shafia_analytics}')
        self.stdout.write(f'شفية (بعد): {new_shafia}')
        self.stdout.write(f'امباركة (قبل): {list(imbaraka.analytics_assignments or [])}')
        self.stdout.write(f'امباركة (بعد): {imbaraka_analytics}')
        self.stdout.write('')

        # 4. تحديث TeacherAssignment (الإسناد في الموارد البشرية) إن وُجد
        shafia_ta = list(TeacherAssignment.objects.filter(teacher=shafia))
        imbaraka_ta = list(TeacherAssignment.objects.filter(teacher=imbaraka))

        for ta in shafia_ta:
            if any(k in (ta.subject or '') for k in math_subject_keys):
                if not dry_run:
                    ta.teacher = imbaraka
                    ta.save()
                self.stdout.write(f'نقل TeacherAssignment الرياضيات من شفية إلى امباركة: {ta.subject} {ta.classes}')

        if not dry_run:
            shafia.analytics_assignments = new_shafia
            shafia.save(update_fields=['analytics_assignments'])
            imbaraka.analytics_assignments = imbaraka_analytics
            imbaraka.save(update_fields=['analytics_assignments'])
            self.stdout.write(self.style.SUCCESS('تم حفظ التعديلات بنجاح.'))
        else:
            self.stdout.write(self.style.WARNING('لم يتم الحفظ (وضع التجربة). شغّل بدون --dry-run للتطبيق.'))

    def _list_teachers(self, teachers):
        self.stdout.write('الأساتذة الحاليون:')
        for t in teachers[:20]:
            self.stdout.write(f'  - id={t.id} | {t.last_name} {t.first_name}')
