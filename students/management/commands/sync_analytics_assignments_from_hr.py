"""
ملء إسناد التحليل (analytics_assignments) من إسناد الموارد البشرية لجميع الأساتذة.
يُستخدم عندما لا تظهر أقسام الأستاذ عند الفلترة رغم وجودها في الموارد البشرية.

استخدام:
  python manage.py sync_analytics_assignments_from_hr
  python manage.py sync_analytics_assignments_from_hr --dry-run
"""
from django.core.management.base import BaseCommand
from students.models import Employee, TeacherAssignment


def _norm_subj(t):
    if not t:
        return ''
    t = str(t).strip().replace('ـ', '').replace('  ', ' ')
    if t.startswith('ال'):
        t = t[2:].strip()
    return t.lower()


def _subject_matches(s1, s2):
    n1, n2 = _norm_subj(s1), _norm_subj(s2)
    return n1 == n2 or n1 in n2 or n2 in n1 or (s1 and s2 and (s1 in s2 or s2 in s1))


class Command(BaseCommand):
    help = 'ملء إسناد التحليل من الموارد البشرية لجميع الأساتذة'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='عرض التغييرات دون الحفظ')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('وضع التجربة: لن يتم حفظ أي تغيير'))

        teachers = Employee.objects.filter(rank='teacher')
        updated = 0
        for emp in teachers:
            hr_assignments = list(
                TeacherAssignment.objects.filter(teacher=emp).values_list('subject', 'classes')
            )
            if not hr_assignments:
                continue

            current = list(emp.analytics_assignments or [])
            # خريطة مادة -> أقسام من الموارد البشرية
            hr_by_subj = {}
            for subj, classes in hr_assignments:
                if not subj or str(subj).strip() == '/':
                    continue
                subj = str(subj).strip()
                cl = list(classes) if isinstance(classes, list) else ([classes] if classes else [])
                if cl:
                    hr_by_subj[subj] = cl

            if not hr_by_subj:
                continue

            changed = False
            if not current:
                # إسناد التحليل فارغ: نبنيه كاملاً من الموارد البشرية
                current = [{'subject': s, 'classes': list(cl)} for s, cl in hr_by_subj.items()]
                changed = True
            else:
                # ملء الأقسام الفارغة من الموارد البشرية
                for a in current:
                    subj = (a.get('subject') or '').strip()
                    cl = a.get('classes')
                    if not subj:
                        continue
                    if cl and isinstance(cl, list) and len(cl) > 0:
                        continue
                    for hr_subj, hr_cl in hr_by_subj.items():
                        if _subject_matches(subj, hr_subj):
                            a['classes'] = list(hr_cl)
                            changed = True
                            break

            if changed:
                updated += 1
                name = f"{emp.last_name or ''} {emp.first_name or ''}".strip()
                self.stdout.write(f"  تحديث: {name} (id={emp.id})")
                if not dry_run:
                    emp.analytics_assignments = current
                    emp.save(update_fields=['analytics_assignments'])

        self.stdout.write(self.style.SUCCESS(f"تم تحديث {updated} أستاذاً." if not dry_run else f"سيتم تحديث {updated} أستاذاً (dry-run)."))
