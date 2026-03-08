from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings, Employee, SystemMessage, Survey, PendingUpdate, Task, SchoolMemory, UserRole
from datetime import date, datetime
from io import StringIO
import os
import tempfile
from django.conf import settings
import openpyxl
from tablib import Dataset
from .resources import StudentResource
from .import_utils import parse_student_file
from .utils import normalize_arabic
from .utils_sync import sync_photos_logic
from django.db.models import Q

def sync_photos_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and request.user.profile.role != 'director':
        return redirect('dashboard')

    count = sync_photos_logic()
    messages.success(request, f"تمت مزامنة {count} صورة بنجاح.")
    return redirect('settings')

def pending_updates_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    pass

    updates = PendingUpdate.objects.all().order_by('-timestamp')
    context = {
        'updates': updates,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': True
    }
    return render(request, 'students/pending_updates.html', context)

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'students/landing.html')

def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')

    # Strict Role Redirection based on Permissions
    try:
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            role = profile.role

            if role == 'director':
                pass # Continue to dashboard
            elif profile.has_perm('access_canteen'):
                return redirect('canteen_home')
            elif profile.has_perm('access_library'):
                return redirect('library_home')
            elif profile.has_perm('access_management'):
                return redirect('students_management')
            elif profile.has_perm('access_archive'):
                return redirect('archive_home')
            else:
                pass # Default dashboard for others (Teachers)
        else:
            # No profile (e.g., admin). If not superuser, redirect
            if not request.user.is_superuser:
                logout(request)
                return redirect('canteen_landing')

    except Exception:
        logout(request)
        return redirect('canteen_landing')

    # Teacher Assignment Logic
    assigned_students = None
    teacher_classes = []

    if hasattr(request.user, 'employee_hr') and request.user.employee_hr.rank == 'teacher':
        assignments = TeacherAssignment.objects.filter(teacher=request.user.employee_hr)
        for assign in assignments:
            if assign.classes:
                teacher_classes.extend(assign.classes)

        # Remove duplicates
        teacher_classes = list(set(teacher_classes))
        if teacher_classes:
            assigned_students = Student.objects.filter(class_name__in=teacher_classes).order_by('class_name', 'last_name')

    # Detailed Stats for Dashboard Table
    from django.db.models import Count

    # Group by Level and Attendance System
    raw_stats = Student.objects.values('academic_year', 'attendance_system').annotate(count=Count('id')).order_by('academic_year')

    # Pivot Data: { '1AM': {'half': 10, 'ext': 5, 'total': 15}, ... }
    stats_map = {}
    for item in raw_stats:
        lvl = item['academic_year'] or 'غير محدد'
        sys = item['attendance_system']
        count = item['count']

        if lvl not in stats_map:
            stats_map[lvl] = {'level': lvl, 'half': 0, 'ext': 0, 'total': 0}

        stats_map[lvl]['total'] += count
        if sys == 'نصف داخلي':
            stats_map[lvl]['half'] += count
        else: # خارجي or others
            stats_map[lvl]['ext'] += count

    # Convert to sorted list
    detailed_stats = sorted(stats_map.values(), key=lambda x: x['level'])

    context = {
        'total_students': Student.objects.count(),
        'half_board_count': Student.objects.filter(attendance_system='نصف داخلي').count(),
        'db_status': 'متصل',
        'present_today': CanteenAttendance.objects.filter(date=date.today()).count(),
        'absent_today': Student.objects.filter(attendance_system='نصف داخلي').count() - CanteenAttendance.objects.filter(date=date.today()).count(),
        'detailed_stats': detailed_stats,
        'assigned_students': assigned_students,
        'teacher_classes': teacher_classes,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/dashboard.html', context)

def settings_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('manage_settings'):
         return redirect('dashboard')

    context = {
        'total_students': Student.objects.count(),
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/settings.html', context)

def import_eleve_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('import_data'):
         return redirect('dashboard')

    force_manual = request.POST.get('manual_mapping') == 'on'

    if request.method == 'POST' and request.FILES.get('eleve_file'):
        eleve_file = request.FILES['eleve_file']
        temp_path = None

        try:
            _, ext = os.path.splitext(eleve_file.name)
            if not ext: ext = '.xls'

            # Save file safely to a persistent temp location (not auto-deleted immediately)
            # We need it for the confirmation step if manual mapping is used
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in eleve_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            # Make sure Dataset is imported correctly here to prevent UnboundLocalError or memory crash in some views
            from tablib import Dataset

            # Check for Manual Mapping Request OR Preview Logic
            if force_manual:
                # Preview Mode
                from .import_utils import extract_rows_from_file, detect_headers
                # Re-open safely
                with open(temp_path, 'rb') as f:
                    all_rows = list(extract_rows_from_file(f, override_filename=temp_path))

                if not all_rows:
                    messages.error(request, "الملف فارغ أو غير قابل للقراءة.")
                    os.remove(temp_path)
                    return redirect('settings')

                preview_rows = all_rows[:5] # First 5 rows

                # Run detection just to suggest
                HEADER_MAP = {
                    'رقم التعريف': 'student_id_number', 'الرقم': 'student_id_number',
                    'اللقب': 'last_name', 'الاسم': 'first_name',
                    'الاسم واللقب': 'full_name', 'تاريخ الميلاد': 'date_of_birth',
                    'القسم': 'class_name', 'المستوى': 'academic_year',
                    'نظام التمدرس': 'attendance_system', 'رقم القيد': 'enrollment_number',
                    'تاريخ التسجيل': 'enrollment_date', 'اسم الولي': 'guardian_name'
                }
                suggested_mapping, _ = detect_headers(preview_rows, HEADER_MAP)

                # Invert mapping for template (index -> field_name)
                # detect_headers returns {field: index}
                inv_map = {v: k for k, v in suggested_mapping.items()}

                context = {
                    'temp_file_path': temp_path,
                    'preview_rows': preview_rows,
                    'num_columns': range(len(preview_rows[0])) if preview_rows else [],
                    'suggested_mapping': inv_map
                }
                return render(request, 'students/import_preview.html', context)

            # Standard Import Logic
            raw_data = parse_student_file(temp_path)

            if not raw_data:
                messages.error(request, "لم يتم العثور على بيانات صالحة في الملف. جرب تفعيل 'تحديد الأعمدة يدوياً'.")
            else:
                # Check for update flag
                update_existing = request.POST.get('update_existing') == 'on'

                # 2. Create Dataset for django-import-export
                headers = list(raw_data[0].keys())
                dataset = Dataset(headers=headers)

                # Fetch existing IDs if we shouldn't update them, to prevent Unique Constraint errors
                existing_ids = set()
                if not update_existing:
                    existing_ids = set(Student.objects.values_list('student_id_number', flat=True))

                for row in raw_data:
                    sid = str(row.get('student_id_number', '')).strip()
                    if not update_existing and sid in existing_ids:
                        continue # Skip existing to prevent Unique Constraint errors
                    dataset.append([row[h] for h in headers])

                if len(dataset) == 0:
                     messages.warning(request, "كل التلاميذ في الملف موجودون مسبقاً في قاعدة البيانات (لم تقم باختيار 'تحديث').")
                else:
                    # 3. Use Resource to Import
                    resource = StudentResource()

                    # By default import-export handles update gracefully if configured,
                    # but if skip_unchanged=True is the only guard, we want to enforce explicitly.
                    # We pass dry_run=False. The resource class uses import_id_fields=('student_id_number',).
                    # If update_existing=False, we've already stripped existing IDs above.
                    # If update_existing=True, we let import_export update them.

                    result = resource.import_data(dataset, dry_run=False, raise_errors=False)

                    if result.has_errors():
                        # Extract exact errors for user context
                        err_msgs = []
                        for i, err in enumerate(result.row_errors()):
                            for e in err[1]: err_msgs.append(str(e.error))
                        messages.error(request, f"حدثت أخطاء أثناء الاستيراد: {', '.join(set(err_msgs))[:100]}...")
                    else:
                        new_count = result.totals.get('new', 0)
                        update_count = result.totals.get('update', 0)
                        skip_count = result.totals.get('skip', 0)
                        total_processed = new_count + update_count + skip_count

                        msg = f"تمت المعالجة: {total_processed} سجل. (جديد: {new_count}، تحديث: {update_count})."
                        if total_processed == 0:
                            messages.warning(request, "لم يتم استيراد أي بيانات. ربما لم يتم التعرف على الأعمدة؟ حاول استخدام 'تحديد الأعمدة يدوياً'.")
                        else:
                            messages.success(request, msg)

            # Cleanup if not preview mode
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

        except Exception as e:
            messages.error(request, f"خطأ في الملف أو المعالجة: {str(e)}")
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

        return redirect('settings')

    return redirect('settings')

def import_eleve_confirm(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')

    if request.method == 'POST':
        temp_path = request.POST.get('temp_file_path')
        if not temp_path or not os.path.exists(temp_path):
            messages.error(request, "انتهت صلاحية الملف المؤقت. يرجى الرفع مجدداً.")
            return redirect('settings')

        try:
            # Reconstruct header map from POST
            # name="col_0", value="field_name"
            override_indices = {}
            for key, value in request.POST.items():
                if key.startswith('col_') and value:
                    idx = int(key.split('_')[1])
                    override_indices[value] = idx

            if not override_indices:
                messages.error(request, "لم يتم تحديد أي عمود!")
                return redirect('settings')

            # Parse with override
            raw_data = parse_student_file(temp_path, override_header_indices=override_indices)

            if not raw_data:
                 messages.error(request, "فشل تحليل البيانات بالأعمدة المحددة.")
            else:
                # Import
                headers = list(raw_data[0].keys())
                dataset = Dataset(headers=headers)
                for row in raw_data:
                    dataset.append([row[h] for h in headers])

                resource = StudentResource()
                result = resource.import_data(dataset, dry_run=False, raise_errors=True)

                new_count = result.totals.get('new', 0)
                update_count = result.totals.get('update', 0)
                messages.success(request, f"تم الاستيراد بنجاح: {new_count} جديد، {update_count} تحديث.")

        except Exception as e:
            messages.error(request, f"خطأ أثناء الاستيراد: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    return redirect('settings')

def canteen_home(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_canteen'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/canteen.html', context)

def student_list(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_management'):
        return redirect('dashboard')

    # Populate initial list (First 50 for performance)
    students = Student.objects.all().order_by('last_name')[:50]

    context = {
        'students': students,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/student_list.html', context)

def students_management(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_management'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/management.html', context)

def library_home(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_library'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/library.html', context)

def archive_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_archive'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/archive.html', context)

def print_student_cards(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_management'):
        return redirect('dashboard')

    if request.method == 'POST':
        # Check for Select All Matching Mode
        select_all = request.POST.get('select_all_matching') == 'true'

        if select_all:
             # Reconstruct Filter Query
             qs = Student.objects.all().order_by('last_name', 'first_name')
             level = request.POST.get('filter_level')
             cls = request.POST.get('filter_class')
             search = request.POST.get('filter_search')

             if level: qs = qs.filter(academic_year=level)
             if cls: qs = qs.filter(class_name=cls)
             if search:
                 norm_search = normalize_arabic(search)
                 q_obj = Q(student_id_number__icontains=search) | \
                         Q(first_name__icontains=search) | \
                         Q(last_name__icontains=search)
                 if norm_search != search:
                     q_obj |= Q(first_name__icontains=norm_search) | \
                              Q(last_name__icontains=norm_search)
                 if 'ه' in search:
                      alt = search.replace('ه', 'ة')
                      q_obj |= Q(first_name__icontains=alt) | Q(last_name__icontains=alt)
                 if 'ة' in search:
                      alt = search.replace('ة', 'ه')
                      q_obj |= Q(first_name__icontains=alt) | Q(last_name__icontains=alt)
                 qs = qs.filter(q_obj)

             students = qs
        else:
             student_ids = request.POST.getlist('student_ids')
             students = Student.objects.filter(id__in=student_ids).order_by('last_name')
    else:
        # Fallback or empty
        students = []

    settings = SchoolSettings.objects.first()
    school_name = settings.name if settings else "اسم المؤسسة"
    academic_year = settings.academic_year if settings else "2024/2025"

    context = {
        'students': students,
        'school_name': school_name,
        'academic_year': academic_year
    }
    return render(request, 'students/print_cards.html', context)

# --- New Modules ---

from .models import TeacherAssignment, ClassAlias, Student
from .ai_utils import analyze_assignment_document, analyze_global_assignment_content
import difflib

def assignment_matching_view(request):
    """
    Wizard-style interface for matching AI-extracted assignment data.
    Steps:
    1. Map Classes (الأقسام)
    2. Map Subjects (المواد)
    3. Map Teachers & Finalize Assignment (الأساتذة والإسناد)
    """
    if not request.user.is_authenticated:
        return redirect('canteen_landing')

    step = int(request.GET.get('step', 1))

    # Session handling
    if 'ai_extracted_data' not in request.session:
        # Initial Extraction if coming from file upload redirect
        temp_path = request.session.get('assignment_temp_path')
        if not temp_path or not os.path.exists(temp_path):
            messages.error(request, "انتهت صلاحية الجلسة أو الملف غير موجود.")
            return redirect('hr_home')

        try:
            candidates = analyze_global_assignment_content(temp_path)
            if not candidates:
                messages.error(request, "لم يتمكن الذكاء الاصطناعي من استخراج بيانات صالحة. تأكد من جودة الملف.")
                return redirect('hr_home')

            request.session['ai_extracted_data'] = candidates
            # Clean up temp file
            try: os.remove(temp_path)
            except: pass
            if 'assignment_temp_path' in request.session:
                del request.session['assignment_temp_path']
        except Exception as e:
            messages.error(request, f"خطأ في تحليل الملف: {e}")
            return redirect('hr_home')

    candidates = request.session.get('ai_extracted_data', [])

    if request.method == 'POST':
        if step == 1:
            # Handle Class Mapping Submission
            # The form submits key-value pairs: class_map_[original_class] = "Mapped Class"
            for c in candidates:
                new_classes = []
                for cl in c['classes']:
                    mapped_val = request.POST.get(f'class_map_{cl}')
                    if mapped_val and mapped_val.strip():
                        # Save mapping to ClassAlias globally for future use if it's different
                        if mapped_val.strip() != cl:
                             parts = mapped_val.strip().rsplit(' ', 1)
                             if len(parts) == 2:
                                  ClassAlias.objects.update_or_create(
                                      alias=cl,
                                      defaults={'canonical_level': parts[0], 'canonical_class': parts[1]}
                                  )
                        new_classes.append(mapped_val.strip())
                    else:
                        new_classes.append(cl) # Keep original if nothing entered
                c['classes'] = list(set(new_classes))

            request.session['ai_extracted_data'] = candidates
            return redirect(f"{request.path}?step=2")

        elif step == 2:
            # Handle Subject Mapping Submission
            for c in candidates:
                mapped_subj = request.POST.get(f"subj_map_{c['subject']}")
                if mapped_subj and mapped_subj.strip():
                    c['subject'] = mapped_subj.strip()

            request.session['ai_extracted_data'] = candidates
            return redirect(f"{request.path}?step=3")

        elif step == 3:
            # Handle Final Teacher Mapping & Save
            count = 0
            for idx, c in enumerate(candidates):
                action = request.POST.get(f'match_{idx}')
                if action == 'ignore': continue

                final_name = request.POST.get(f'name_{idx}', c['name'])

                subjects = request.POST.getlist(f'subject_{idx}[]')
                block_indices = request.POST.getlist(f'block_indices_{idx}[]')

                assignments = []
                # Safely pair subjects with their specific block index to fetch the exact classes array
                for j, subject in enumerate(subjects):
                    if subject.strip() and j < len(block_indices):
                        block_idx = block_indices[j]
                        classes_checked = request.POST.getlist(f'classes_{idx}_{block_idx}[]')
                        assignments.append({
                            'subject': subject.strip(),
                            'classes': classes_checked
                        })

                main_subject = subjects[0].strip() if subjects else c['subject']

                teacher = None
                if action == 'create_new':
                    parts = final_name.split()
                    ln = parts[0] if parts else "غير معروف"
                    fn = " ".join(parts[1:]) if len(parts) > 1 else ""
                    teacher = Employee.objects.create(
                        last_name=ln, first_name=fn,
                        rank='teacher', subject=main_subject
                    )
                else:
                    try:
                        teacher = Employee.objects.get(id=action)
                        if main_subject and main_subject != '/':
                            teacher.subject = main_subject
                            teacher.save()
                        # Clear existing assignments when updating via wizard to prevent duplicates
                        TeacherAssignment.objects.filter(teacher=teacher).delete()
                    except Employee.DoesNotExist:
                        continue

                if teacher:
                    for assignment in assignments:
                        if assignment.get('subject'):
                            TeacherAssignment.objects.create(
                                teacher=teacher,
                                subject=assignment['subject'],
                                classes=assignment.get('classes', [])
                            )
                    count += 1

            messages.success(request, f"تم حفظ الإسناد لـ {count} أستاذ وربطهم بنجاح.")
            if 'ai_extracted_data' in request.session:
                del request.session['ai_extracted_data']
            return redirect('hr_home')

    # --- GET Display Logic for Steps ---
    context = {'step': step, 'candidates': candidates}

    if step == 1:
        # Extract unique classes
        extracted_classes = set()
        for c in candidates:
            for cl in c['classes']:
                extracted_classes.add(cl)

        # Get DB valid classes to build a dropdown
        db_combinations = list(
            Student.objects.exclude(academic_year__isnull=True).exclude(academic_year__exact='')
            .exclude(class_name__isnull=True).exclude(class_name__exact='')
            .values_list('academic_year', 'class_name').distinct()
        )
        db_classes = [f"{lvl} {cls}" for lvl, cls in db_combinations]

        # Pre-process matches
        aliases = dict(ClassAlias.objects.values_list('alias', 'canonical_class'))

        class_mapping_data = []
        for cl in extracted_classes:
            suggested = cl
            if cl in db_classes:
                pass # perfect match
            elif cl in aliases:
                suggested = aliases[cl]

            class_mapping_data.append({
                'original': cl,
                'suggested': suggested
            })

        context['class_mapping_data'] = class_mapping_data
        context['db_classes'] = db_classes

    elif step == 2:
        extracted_subjects = set(c['subject'] for c in candidates if c['subject'] and c['subject'] != '/')

        # Get subjects from Grade model
        from .models import Grade
        grade_subjects = list(Grade.objects.values_list('subject', flat=True).distinct())

        # Merge with common subjects as a fallback
        common_subjects = [
            'رياضيات', 'لغة عربية', 'لغة فرنسية', 'لغة إنجليزية', 'تاريخ وجغرافيا',
            'علوم طبيعية', 'فيزياء', 'تربية إسلامية', 'تربية مدنية', 'تربية بدنية',
            'تربية تشكيلية', 'تربية موسيقية', 'إعلام آلي', 'لغة أمازيغية'
        ]

        standard_subjects = list(set(grade_subjects + common_subjects))
        standard_subjects.sort()

        subject_mapping_data = []
        for subj in extracted_subjects:
            suggested = subj
            # Simple substring matching for suggestion
            for s in standard_subjects:
                if s in subj or subj in s:
                    suggested = s
                    break
            subject_mapping_data.append({
                'original': subj,
                'suggested': suggested
            })

        context['subject_mapping_data'] = subject_mapping_data
        context['standard_subjects'] = standard_subjects

    elif step == 3:
        from .models_mapping import ClassShortcut
        context['all_classes'] = list(ClassShortcut.objects.values_list('shortcut', flat=True).distinct())
        context['all_classes'].sort()
        all_teachers = Employee.objects.filter(rank='teacher').order_by('last_name')

        def get_similarity(s1, s2):
            if not s1 or not s2: return 0.0
            return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

        import json

        # Make all_classes whitespace-normalized for robust matching
        normalized_all_classes = {cl.replace(" ", ""): cl for cl in context['all_classes']}

        # Advanced normalization for Arabic words extracted by AI that didn't match directly
        arabic_level_map = {
            'أولى': '1', 'الاولى': '1', 'الأولى': '1', 'اولى': '1',
            'ثانية': '2', 'الثانية': '2', 'ثانيه': '2', 'الثانيه': '2',
            'ثالثة': '3', 'الثالثة': '3', 'ثالثه': '3', 'الثالثه': '3',
            'رابعة': '4', 'الرابعة': '4', 'رابعه': '4', 'الرابعه': '4'
        }

        import re
        for c in candidates:
            mapped_classes = []
            for cl in c.get('classes', []):
                cl_orig = cl.strip()
                cl_norm = cl_orig.replace(" ", "")

                # Perfect Match
                if cl_norm in normalized_all_classes:
                    mapped_classes.append(normalized_all_classes[cl_norm])
                    continue

                # If it's already properly formatted (like "4م1") but just missing from normalized_all_classes
                # (e.g., custom class not in DB yet), don't mutate it further.
                if re.match(r'^\d+م\d+$', cl_norm):
                     mapped_classes.append(cl_norm)
                     continue

                # Heuristic extraction for common formats (e.g. "أولى 1", "4 متوسط 2")
                all_nums = re.findall(r'\d+', cl_orig)
                mapped_digit = None
                class_num = None

                # Find Arabic words representing the level
                for arb_word, digit in arabic_level_map.items():
                    if arb_word in cl_orig:
                        mapped_digit = digit
                        break

                if mapped_digit:
                     class_num = all_nums[0] if len(all_nums) > 0 else None
                else:
                     if len(all_nums) >= 2:
                          mapped_digit = all_nums[0]
                          class_num = all_nums[1]
                     elif len(all_nums) == 1:
                          mapped_digit = all_nums[0]
                          class_num = all_nums[0]

                if mapped_digit and class_num:
                    constructed_shortcut = f"{mapped_digit}م{class_num}"
                    if constructed_shortcut in normalized_all_classes:
                        mapped_classes.append(normalized_all_classes[constructed_shortcut])
                    else:
                        mapped_classes.append(constructed_shortcut)
                else:
                    mapped_classes.append(cl_orig)

            c['classes'] = mapped_classes

            best_score = 0.0
            best_match = None
            c_norm = (c.get('name') or '').strip()

            for t in all_teachers:
                t_ln = t.last_name or ''
                t_fn = t.first_name or ''

                t_full = f"{t_ln} {t_fn}".strip()
                t_rev = f"{t_fn} {t_ln}".strip()

                if t_ln and t_fn and t_ln in c_norm and t_fn in c_norm:
                    score = 1.0
                elif t_ln and t_ln in c_norm and len(t_ln) > 3:
                    score = 0.8
                else:
                    score = max(
                        get_similarity(c_norm, t_full),
                        get_similarity(c_norm, t_rev),
                        get_similarity(c_norm, t_ln)
                    )

                if score > best_score:
                    best_score = score
                    best_match = t

            if best_score >= 0.6 and best_match:
                c['suggested_id'] = best_match.id
                c['auto_action'] = str(best_match.id)
            else:
                c['auto_action'] = 'create_new'

                c['classes_json'] = json.dumps(c.get('classes', []))

        context['all_teachers'] = all_teachers

    return render(request, 'students/assignment_match.html', context)

def hr_home(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'import_file' and request.FILES.get('file'):
            file = request.FILES['file']
            # Save strictly to disk for processing
            temp_path = None
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                    for chunk in file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                from .import_utils import parse_hr_file
                employees_data = parse_hr_file(temp_path)

                count = 0
                for emp in employees_data:
                    # Parse Rank: Use what's in the file, map to system keys
                    raw_rank = emp.get('rank', '').strip()

                    # Logic: If 'أستاذ' is in rank, it's a teacher.
                    # If 'عامل مهني' is in rank, it's a worker.
                    # Everything else (Director, Admin, Steward, Data Entry) is 'admin'.

                    sys_rank = 'admin' # Default to admin for general staff

                    # Improved Classification Logic based on User Feedback
                    if 'أستاذ' in raw_rank:
                        sys_rank = 'teacher'
                    # Explicitly catch "Aoun Khidma" (Service Agent) regardless of level (1, 2, 3...)
                    elif 'عامل مهني' in raw_rank or 'عون الخدمة' in raw_rank or 'عون خدمة' in raw_rank or 'عون وقاية' in raw_rank or 'منظف' in raw_rank or 'حارس' in raw_rank:
                         # "Service Agent", "Prevention Agent", "Worker", "Cleaner", "Guard" -> Worker
                         sys_rank = 'worker'
                    elif 'عون' in raw_rank:
                         # "Agent" alone (Admin Agent, Office Agent, Data Entry Agent) -> Admin
                         # Check if explicitly admin-related keywords follow "Agent"
                         if any(x in raw_rank for x in ['إدارة', 'مكتب', 'حفظ', 'رقن', 'بيانات', 'محاسب']):
                             sys_rank = 'admin'
                         else:
                             # Default fallback for generic "Agent" to Admin as per "First point" in request
                             sys_rank = 'admin'

                    # Validation: Filter out header rows that might have slipped through
                    # If 'rank' literally contains "الرتبة" or "rank", skip
                    if 'الرتبة' in raw_rank or 'اللقب' in emp.get('last_name', ''):
                        continue

                    # Handle Subject
                    subject = emp.get('subject', '/')
                    if sys_rank != 'teacher':
                        subject = "/"

                    # Dates Parsing
                    def parse_d(val):
                        if not val: return None
                        if isinstance(val, (date, datetime)): return val
                        try: return datetime.strptime(str(val).strip(), '%Y-%m-%d').date()
                        except: pass
                        try: return datetime.strptime(str(val).strip(), '%d/%m/%Y').date()
                        except: pass
                        return None

                    dob = parse_d(emp.get('date_of_birth'))
                    eff_date = parse_d(emp.get('effective_date'))

                    # Duplicate Prevention Logic:
                    # 1. Try to find by unique Employee Code if present
                    # 2. Try to find by Name + DOB if Code is generic/missing

                    emp_code = emp.get('employee_code')
                    ln = emp.get('last_name', '')
                    fn = emp.get('first_name', '')

                    # Search for existing
                    existing = None
                    if emp_code:
                        existing = Employee.objects.filter(employee_code=emp_code).first()

                    if not existing and ln and fn:
                        existing = Employee.objects.filter(
                            last_name=ln,
                            first_name=fn,
                            date_of_birth=dob
                        ).first()

                    # Data dict
                    defaults={
                        'last_name': ln,
                        'first_name': fn,
                        'date_of_birth': dob,
                        'rank': sys_rank,
                        'role': raw_rank,
                        'subject': subject,
                        'grade': emp.get('grade', ''),
                        'effective_date': eff_date,
                        'phone': emp.get('phone', ''),
                        'email': emp.get('email', ''),
                    }

                    if existing:
                        for key, value in defaults.items():
                            setattr(existing, key, value)
                        existing.save()
                    else:
                        Employee.objects.create(employee_code=emp_code, **defaults)

                    count += 1

                messages.success(request, f"تم استيراد/تحديث {count} موظف.")
            except Exception as e:
                messages.error(request, f"خطأ في الملف: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except: pass
            return redirect('hr_home')

        elif action == 'add_manual':
            try:
                edit_id = request.POST.get('edit_id')

                # Manual entry allows direct setting of both System Rank and Role Title
                sys_rank = request.POST.get('rank') # Comes from the dropdown (teacher, worker, admin)
                role_title = request.POST.get('role') # Comes from the text input (e.g., "Professional Worker Lvl 1")

                data = {
                    'employee_code': request.POST.get('employee_code'),
                    'last_name': request.POST.get('last_name'),
                    'first_name': request.POST.get('first_name'),
                    'rank': sys_rank,
                    'role': role_title, # Explicit manual title
                    'subject': request.POST.get('subject') if sys_rank == 'teacher' else '/',
                    'grade': request.POST.get('grade'),
                    'phone': request.POST.get('phone'),
                    'email': request.POST.get('email'),
                    'date_of_birth': request.POST.get('date_of_birth') or None,
                    'effective_date': request.POST.get('effective_date') or None,
                }

                if edit_id:
                    Employee.objects.filter(id=edit_id).update(**data)
                    messages.success(request, "تم تعديل الموظف بنجاح.")
                else:
                    Employee.objects.create(**data)
                    messages.success(request, "تمت إضافة الموظف بنجاح.")
            except Exception as e:
                messages.error(request, f"خطأ: {e}")
            return redirect('hr_home')

        elif action == 'manual_assign_single':
            try:
                teacher_id = request.POST.get('teacher_id')
                payload = request.POST.get('assignments_payload')

                teacher = Employee.objects.get(id=teacher_id)
                TeacherAssignment.objects.filter(teacher=teacher).delete()

                assignments = []
                if payload:
                    import json
                    try:
                        assignments = json.loads(payload)
                    except:
                        pass

                main_subject = ''
                for assign in assignments:
                    subj = assign.get('subject', '').strip()
                    if subj:
                        if not main_subject: main_subject = subj
                        TeacherAssignment.objects.create(
                            teacher=teacher,
                            subject=subj,
                            classes=assign.get('classes', [])
                        )

                if main_subject:
                    teacher.subject = main_subject
                    teacher.save()

                messages.success(request, f'تم إسناد المادة {main_subject} للأستاذ بنجاح.')
            except Exception as e:
                messages.error(request, f'خطأ أثناء الحفظ: {e}')
            return redirect('hr_home')

        elif action == 'import_assignment_global':
            file = request.FILES.get('assignment_file')
            if file:
                try:
                    # Save temporary file for analysis
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                        for chunk in file.chunks():
                            tmp.write(chunk)
                        tmp_path = tmp.name

                    # Clear old extracted data if any
                    if 'ai_extracted_data' in request.session:
                        del request.session['ai_extracted_data']

                    # Store path in session to pass to matching view
                    request.session['assignment_temp_path'] = tmp_path
                    from django.urls import reverse
                    return redirect(f"{reverse('assignment_matching_view')}?step=1")

                except Exception as e:
                    messages.error(request, f"خطأ في رفع الملف: {e}")
            return redirect('hr_home')

    # Filtering
    rank_filter = request.GET.get('rank')
    employees = Employee.objects.all().order_by('last_name')
    if rank_filter:
        employees = employees.filter(rank=rank_filter)

    # Counts
    counts = {
        'teachers': Employee.objects.filter(rank='teacher').count(),
        'workers': Employee.objects.filter(rank='worker').count(),
        'admins': Employee.objects.filter(rank='admin').count(),
        'total': Employee.objects.count()
    }

    # Get All Classes for Dropdown
    from .models_mapping import ClassShortcut, ensure_class_shortcuts_populated

    # Ensure database is fully populated with actual student classes
    ensure_class_shortcuts_populated()

    shortcut_classes = list(ClassShortcut.objects.values_list('shortcut', flat=True).distinct())

    # Also fetch existing assignments so teachers don't lose custom classes
    assigned_classes = []
    for ta in TeacherAssignment.objects.all():
        assigned_classes.extend(ta.classes)

    all_classes = list(set(shortcut_classes + assigned_classes))
    all_classes.sort()

    # Auto-Select Logic (If file was uploaded previously)
    auto_select_data = request.session.pop('auto_select_assignment', None)

    context = {
        'employees': employees,
        'current_rank': rank_filter,
        'counts': counts,
        'all_classes': all_classes,
        'auto_select_data': auto_select_data, # Pass to template
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/hr.html', context)

def hr_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    get_object_or_404(Employee, pk=pk).delete()
    messages.success(request, "تم الحذف")
    return redirect('hr_home')

def parents_home(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_parents'):
        return redirect('dashboard')

    # Just list students with parent info
    # Optimize: only fetch needed fields
    students = Student.objects.only(
        'id', 'first_name', 'last_name', 'date_of_birth',
        'guardian_name', 'mother_name', 'guardian_phone', 'address',
        'class_name', 'student_id_number', 'gender'
    ).all().order_by('last_name')

    context = {
        'students': students,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/parents.html', context)

def guidance_home(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_guidance'):
        return redirect('dashboard')

    ai_suggestion = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ai_suggest':
            topic = request.POST.get('topic')
            target = request.POST.get('target_audience')
            from .ai_utils import AIService
            ai = AIService(user=request.user)

            # Rich context prompt based on user's feedback
            prompt = f"""
            أنت خبير في القياس والتقويم التربوي وعلم النفس المدرسي.
            المطلوب: تصميم هيكل استبيان احترافي وعميق حول الموضوع: "{topic}".
            الفئة المستهدفة: {target}.

            يجب أن تتبع المنهجية العلمية التالية في إجابتك:
            1. **تحديد الأهداف:** ماذا نريد أن نقيس بدقة؟
            2. **صياغة المقدمة:** فقرة تشرح الهدف وتطمئن المشارك (سرية البيانات).
            3. **محاور الاستبيان:** اقترح 3-4 محاور رئيسية تغطي الموضوع.
            4. **نماذج الأسئلة:**
               - أسئلة مغلقة (نعم/لا) أو متعددة الاختيارات.
               - أسئلة مقياس ليكرت (موافق بشدة - موافق - محايد - غير موافق...).
               - سؤال مفتوح في النهاية للمقترحات.
            5. **نصائح للتوزيع والتحليل:** كيف يتم نشر الاستبيان وتحليل نتائجه لهذه الفئة تحديداً.

            تنبيه هام:
            - إذا كان الجمهور "تلاميذ صغار": استخدم لغة بسيطة جداً ومباشرة.
            - إذا كان "أولياء": استخدم لغة رسمية محترمة وواضحة.
            - إذا كان "أساتذة": استخدم مصطلحات تربوية مهنية.

            قدم الإجابة بتنسيق Markdown منظم (عناوين، نقاط، جداول إن أمكن).
            """

            # Use 'gemini_full' mode to ensure depth and prevent "admin assistant" constraints
            ai_suggestion = ai.generate_response("أنت خبير تربوي ومستشار توجيه.", prompt, rag_enabled=False, mode='gemini_full')

        elif action == 'create_survey':
            try:
                Survey.objects.create(
                    title=request.POST.get('title'),
                    description=request.POST.get('description'),
                    target_audience=request.POST.get('target_audience'),
                    link=request.POST.get('link')
                )
                messages.success(request, "تم إنشاء الاستبيان")
                return redirect('guidance_home')
            except Exception as e:
                messages.error(request, "خطأ في الإنشاء")

    surveys = Survey.objects.all().order_by('-created_at')
    context = {
        'surveys': surveys,
        'ai_suggestion': ai_suggestion,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/guidance.html', context)

def ai_manual_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    pass

    return render(request, 'students/ai_manual.html')

def ai_chat_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_ai_chat')):
        return redirect('dashboard')

    if request.method == 'POST':
        from .ai_utils import AIService
        from django.http import JsonResponse

        query = request.POST.get('query')
        # Mode requested by UI (will be checked against permissions inside AIService)
        requested_mode = request.POST.get('mode', None)

        # Set Director Default to 'gemini_full' if mode is not specified or ambiguous
        if (hasattr(request.user, 'profile') and request.user.profile.role == 'director') or request.user.is_superuser:
            if not requested_mode or requested_mode == 'rag':
                 requested_mode = 'gemini_full'

        # Pass current user for permission check
        ai = AIService(user=request.user)

        # System instructions base (overridden by mode logic in generate_response)
        sys_instr = "أنت مساعد مدير المدرسة."

        rag_enabled = (requested_mode == 'rag' or requested_mode is None)

        # Pass analytics data context if mode is analytics
        if requested_mode == 'analytics':
            analytics_data = request.session.get('analytics_markdown', '')
            if analytics_data:
                sys_instr += f"\n\nإليك بيانات الإحصائيات الحالية (Markdown Table):\n{analytics_data}\n\nيرجى قراءة هذه البيانات بدقة والإجابة على سؤال المستخدم بناءً عليها بصفة حصرية."

        response_text = ai.generate_response(sys_instr, query, rag_enabled=rag_enabled, mode=requested_mode)
        return JsonResponse({'response': response_text})

    return render(request, 'students/ai_chat.html')

# --- AI & Task UI Views ---

def tasks_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_tasks')):
        return redirect('dashboard')

    # Simple permission check: must be logged in
    # Director sees dashboard for managing tasks
    # Regular users see their list

    is_director = request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser

    context = {
        'is_director': is_director,
        'roles': UserRole.objects.all(),
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
    }
    return render(request, 'students/tasks.html', context)

def ai_control_panel(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_ai_control')):
        return redirect('dashboard')

    context = {
        'is_director': True,
        'memories': SchoolMemory.objects.all().order_by('-created_at')
    }
    return render(request, 'students/ai_control.html', context)


def analytics_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_analytics')):
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'import_grades' and request.FILES.get('file'):
            file = request.FILES['file']
            term = request.POST.get('term')
            import tempfile
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                    for chunk in file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                from .grade_importer import process_grades_file
                count, msg = process_grades_file(temp_path, term)
                if count > 0:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg)
            except Exception as e:
                messages.error(request, f"خطأ في معالجة الملف: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    try: os.remove(temp_path)
                    except: pass

            return redirect('analytics_dashboard')

    from .models import Grade, Student
    from .analytics_utils import analyze_grades_locally
    import re

    # Get distinct academic years (levels) and classes
    levels = list(Student.objects.values_list('academic_year', flat=True).distinct())
    levels = [lvl for lvl in levels if lvl]

    classes_qs = Student.objects.values('academic_year', 'class_name').distinct()
    class_map = {}
    from .analytics_utils import format_class_name
    for item in classes_qs:
        lvl = item['academic_year'] or 'غير محدد'
        raw_cls = item['class_name']
        if raw_cls:
            cls = format_class_name(lvl, raw_cls)
            if lvl not in class_map:
                class_map[lvl] = []
            if cls not in class_map[lvl]:
                class_map[lvl].append(cls)

    # Sort classes using custom logic (e.g. numerical order)
    def custom_sort(item):
        if not item: return (999, item)
        match = re.search(r'\d+', item)
        if match:
            return (int(match.group()), item)
        return (999, item)

    for lvl in class_map:
        class_map[lvl] = sorted(class_map[lvl], key=custom_sort)

    selected_term = request.GET.get('term', '')
    selected_level = request.GET.get('level', '')
    selected_class = request.GET.get('class_name', '')
    selected_teacher_id = request.GET.get('teacher_id', '')
    selected_subject = request.GET.get('subject', '')

    grades_qs = Grade.objects.all()
    if selected_term:
        grades_qs = grades_qs.filter(term=selected_term)

    # Subject Filtering
    if selected_subject:
        import django.db.models as models
        grades_qs = grades_qs.filter(models.Q(subject__icontains=selected_subject))

    # Teacher Assignment Filtering
    if selected_teacher_id:
        from .models import Employee, TeacherAssignment
        from .models_mapping import ClassShortcut
        try:
            teacher = Employee.objects.get(id=selected_teacher_id)
            assignments = TeacherAssignment.objects.filter(teacher=teacher)

            # If a subject is selected, only filter by classes for THAT specific subject
            if selected_subject:
                assignments = assignments.filter(subject__icontains=selected_subject)

            teacher_classes = []
            teacher_subjects = []
            for assign in assignments:
                if assign.classes:
                    teacher_classes.extend(assign.classes)
                if assign.subject and assign.subject != '/' and assign.subject not in teacher_subjects:
                    teacher_subjects.append(assign.subject)

            # Remove duplicates
            teacher_classes = list(set(teacher_classes))

            # Map shortcuts back to full names if possible to filter the DB correctly
            full_class_names = []
            for tc in teacher_classes:
                shortcut_obj = ClassShortcut.objects.filter(shortcut=tc).first()
                if shortcut_obj:
                    full_class_names.append(shortcut_obj.full_name)
                full_class_names.append(tc) # Also keep the raw one just in case
            full_class_names = list(set(full_class_names))

            if full_class_names:
                import django.db.models as models
                q_classes = models.Q()
                from .analytics_utils import unformat_class_name
                for cls in full_class_names:
                    raw_c = unformat_class_name(cls)
                    if raw_c and raw_c.isdigit():
                        q_classes |= models.Q(student__class_name=cls) | models.Q(student__class_name=raw_c) | models.Q(student__class_name__endswith=f" {raw_c}") | models.Q(student__class_name__endswith=f"م{raw_c}") | models.Q(student__class_name__icontains=raw_c)
                    else:
                        q_classes |= models.Q(student__class_name=cls)
                grades_qs = grades_qs.filter(q_classes)

            if teacher_subjects and not selected_subject:
                # If no subject is explicitly selected via dropdown, filter by ALL the teacher's subjects
                q_subjs = models.Q()
                for subj in teacher_subjects:
                    q_subjs |= models.Q(subject__icontains=subj)
                grades_qs = grades_qs.filter(q_subjs)

            # Update subjects_list for dropdown to only show THIS teacher's subjects
            if not selected_subject:
                 subjects_list = teacher_subjects

        except Employee.DoesNotExist:
            pass
    else:
        if selected_level:
            import django.db.models as models
            grades_qs = grades_qs.filter(
                models.Q(student__academic_year=selected_level) |
                models.Q(student__academic_year__icontains=selected_level.replace(' متوسط', '').strip())
            )
        if selected_class:
            from .analytics_utils import unformat_class_name
            import django.db.models as models
            raw_class = unformat_class_name(selected_class)
            if raw_class and raw_class.isdigit():
                grades_qs = grades_qs.filter(
                    models.Q(student__class_name=selected_class) |
                    models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__endswith=f"م{raw_class}") |
                    models.Q(student__class_name__icontains=raw_class)
                )
            else:
                grades_qs = grades_qs.filter(student__class_name=selected_class)

    local_stats = analyze_grades_locally(grades_qs)

    token_cost = 0
    if local_stats and local_stats.get('markdown_data'):
        request.session['analytics_markdown'] = local_stats['markdown_data']

        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            token_cost = len(encoding.encode(local_stats['markdown_data']))
        except Exception:
            token_cost = len(local_stats['markdown_data']) // 4

    import json

    # Get Dynamic Subjects List
    subjects_list = [s for s in Grade.objects.values_list('subject', flat=True).distinct() if s and not s.startswith('معدل')]
    subjects_list.sort()

    # Get Teachers List for Dropdown
    from .models import Employee
    teachers = Employee.objects.filter(rank='teacher').order_by('last_name')

    context = {
        'page_title': 'تحليل النتائج',
        'local_stats': local_stats,
        'levels': levels,
        'class_map_json': json.dumps(class_map),
        'token_cost': token_cost,
        'teachers': teachers,
        'subjects_list': subjects_list,
        'selected_teacher_id': selected_teacher_id
    }
    return render(request, 'students/analytics.html', context)

def advanced_analytics_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_advanced_analytics')):
        return redirect('dashboard')

    from .models import Grade
    import pandas as pd

    # Global Filters
    selected_level = request.GET.get('level', '')
    selected_class = request.GET.get('class_name', '')
    selected_teacher_id = request.GET.get('teacher_id', '')
    selected_subject = request.GET.get('subject', '')

    # Retrieve all active grades
    grades_qs = Grade.objects.all()

    # Apply Filters to the QuerySet
    # Compute teacher subjects BEFORE filtering the assignments by selected_subject
    teacher_subjects = []
    if selected_teacher_id:
        from .models import Employee, TeacherAssignment
        from .models_mapping import ClassShortcut
        try:
            teacher = Employee.objects.get(id=selected_teacher_id)
            assignments = TeacherAssignment.objects.filter(teacher=teacher)
            for assign in assignments:
                if assign.subject and assign.subject != '/' and assign.subject not in teacher_subjects:
                    teacher_subjects.append(assign.subject)
        except Employee.DoesNotExist:
            pass

    # Now apply selected_subject filter
    if selected_subject:
        import django.db.models as models
        grades_qs = grades_qs.filter(models.Q(subject__icontains=selected_subject))

    if selected_teacher_id:
        from .models import Employee, TeacherAssignment
        from .models_mapping import ClassShortcut
        try:
            teacher = Employee.objects.get(id=selected_teacher_id)
            assignments = TeacherAssignment.objects.filter(teacher=teacher)

            if selected_subject:
                assignments = assignments.filter(subject__icontains=selected_subject)

            teacher_classes = []
            for assign in assignments:
                if assign.classes:
                    teacher_classes.extend(assign.classes)

            teacher_classes = list(set(teacher_classes))

            # Map shortcuts back to full names if possible to filter the DB correctly
            full_class_names = []
            for tc in teacher_classes:
                shortcut_obj = ClassShortcut.objects.filter(shortcut=tc).first()
                if shortcut_obj:
                    full_class_names.append(shortcut_obj.full_name)
                full_class_names.append(tc) # Also keep the raw one just in case
            full_class_names = list(set(full_class_names))

            if full_class_names:
                import django.db.models as models
                q_classes = models.Q()
                from .analytics_utils import unformat_class_name
                for cls in full_class_names:
                    raw_c = unformat_class_name(cls)
                    if raw_c and raw_c.isdigit():
                        q_classes |= models.Q(student__class_name=cls) | models.Q(student__class_name=raw_c) | models.Q(student__class_name__endswith=f" {raw_c}") | models.Q(student__class_name__endswith=f"م{raw_c}") | models.Q(student__class_name__icontains=raw_c)
                    else:
                        q_classes |= models.Q(student__class_name=cls)
                grades_qs = grades_qs.filter(q_classes)

            if teacher_subjects and not selected_subject:
                import django.db.models as models
                q_subjs = models.Q()
                for subj in teacher_subjects:
                    q_subjs |= models.Q(subject__icontains=subj)
                grades_qs = grades_qs.filter(q_subjs)

            # Note: subjects_list is derived earlier in this view from active grades so we shouldn't necessarily override it,
            # but we will just filter the data correctly.

        except Employee.DoesNotExist:
            pass
    else:
        if selected_level:
            import django.db.models as models
            grades_qs = grades_qs.filter(
                models.Q(student__academic_year=selected_level) |
                models.Q(student__academic_year__icontains=selected_level.replace(' متوسط', '').strip())
            )
        if selected_class:
            from .analytics_utils import unformat_class_name
            import django.db.models as models
            raw_class = unformat_class_name(selected_class)
            if raw_class and raw_class.isdigit():
                grades_qs = grades_qs.filter(
                    models.Q(student__class_name=selected_class) |
                    models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__endswith=f"م{raw_class}") |
                    models.Q(student__class_name__icontains=raw_class)
                )
            else:
                grades_qs = grades_qs.filter(student__class_name=selected_class)

    if not grades_qs.exists():
        messages.warning(request, "لا توجد علامات مسجلة للقيام بتحليل متقدم (أو لا توجد نتائج مطابقة للفلتر).")
        # Don't redirect, render empty dashboard instead so filters remain accessible
        df = pd.DataFrame(columns=['student__id', 'student__gender', 'student__academic_year', 'student__class_name', 'subject', 'term', 'score', 'computed_level'])
    else:
        # Basic logic for advanced stats
        df = pd.DataFrame(list(grades_qs.values('student__id', 'student__gender', 'student__academic_year', 'student__class_name', 'subject', 'term', 'score')))

    from .analytics_utils import format_class_name
    df['student__class_name'] = df.apply(lambda row: format_class_name(row['student__academic_year'], row['student__class_name']), axis=1)

    # Filter out absences
    df = df[df['score'] > 0]

    # Function to get detailed stats per group
    def get_detailed_stats(group_df, group_col):
        stats = {}
        for name, g in group_df.groupby(group_col):
            total = len(g)
            avg = float(round(g['score'].mean(), 2)) if total > 0 else 0.0
            count_above_10 = int(len(g[g['score'] >= 10]))
            success_pct = float(round((count_above_10 / total) * 100, 2)) if total > 0 else 0.0
            stats[str(name)] = {
                'avg': avg,
                'count': total,
                'success_pct': success_pct
            }
        return stats

    # 1. Gender Comparison
    gender_stats = get_detailed_stats(df, 'student__gender') if 'student__gender' in df.columns else {}

    # 2. Terms Comparison
    term_stats = get_detailed_stats(df, 'term')

    # 3. Level/Class Comparison
    class_stats_by_level = {}

    # Try to infer level from class if academic_year is missing
    def infer_level(row):
        ay = str(row['student__academic_year']).strip()
        if ay and ay != 'None' and ay != 'nan':
            return ay
        # Fallback to class name inference
        c_name = str(row['student__class_name']).strip()
        import re
        match = re.search(r'(\d+)\s*(متوسط|م)', c_name)
        if match:
            num = match.group(1)
            return f"{num} متوسط"
        return "غير محدد"

    df['computed_level'] = df.apply(infer_level, axis=1)

    for level, group in df.groupby('computed_level'):
        # Filter out empty or unidentifiable levels
        lvl_str = str(level).strip()
        if not lvl_str or lvl_str == 'None' or lvl_str == 'nan':
            lvl_str = "غير محدد"
        class_stats_by_level[lvl_str] = get_detailed_stats(group, 'student__class_name')

    import json
    import numpy as np
    import scipy.stats as stats

    # 4. Central Tendency and Dispersion measures
    if selected_subject or selected_teacher_id:
        # If analyzing a specific subject/teacher, we calculate based on the specific subject scores
        target_df = df.groupby(['student__id'])['score'].mean().reset_index() if not df.empty else pd.DataFrame(columns=['score'])
    else:
        # Fallback to general average
        general_avg_subjs = [subj for subj in df['subject'].unique() if subj and isinstance(subj, str) and (subj.strip() == 'المعدل العام' or subj.strip().startswith('معدل الفصل'))] if not df.empty else []
        if general_avg_subjs:
            target_df = df[df['subject'].isin(general_avg_subjs)].copy()
        else:
            target_df = df.groupby(['student__id', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index() if not df.empty else pd.DataFrame(columns=['score'])

    active_scores = target_df[target_df['score'] > 0]['score'].dropna() if not target_df.empty else pd.Series(dtype='float64')

    # Cap values to max 20 just in case
    active_scores = active_scores.clip(upper=20.0)

    advanced_stats = {
        'mean': round(active_scores.mean(), 2) if not active_scores.empty else 0,
        'median': round(active_scores.median(), 2) if not active_scores.empty else 0,
        'mode': round(active_scores.mode()[0], 2) if not active_scores.empty and not active_scores.mode().empty else 0,
        'variance': round(active_scores.var(), 2) if len(active_scores) > 1 else 0,
        'std_dev': round(active_scores.std(), 2) if len(active_scores) > 1 else 0,
        'range': round(active_scores.max() - active_scores.min(), 2) if not active_scores.empty else 0,
        'min': round(active_scores.min(), 2) if not active_scores.empty else 0,
        'max': round(active_scores.max(), 2) if not active_scores.empty else 0,
    }

    # 5. Gauss Normal Distribution Data
    gauss_data = {}
    if len(active_scores) > 1:
        mean = advanced_stats['mean']
        std = advanced_stats['std_dev']

        # Create bins for actual data (from 0 to 20, step 1)
        bins = np.arange(0, 22, 1)
        hist, bin_edges = np.histogram(active_scores, bins=bins, density=True)

        # Create continuous x values for the theoretical curve
        x = np.linspace(0, 20, 100)
        y = stats.norm.pdf(x, mean, std) if std > 0 else np.zeros_like(x)

        # We need to pass discrete points to Chart.js for the theoretical curve
        # to align somewhat with the actual distribution bar chart
        discrete_x = np.arange(0, 21, 1)
        discrete_y = stats.norm.pdf(discrete_x, mean, std) if std > 0 else np.zeros_like(discrete_x)

        conclusion = "غير محدد"
        if not pd.isna(std) and not pd.isna(mean):
            if std < 1.5:
                conclusion = "متجانس جداً (متقارب)"
            elif std < 2.5:
                conclusion = "متجانس (توزيع طبيعي)"
            elif std < 3.5:
                conclusion = "متجانس قليلاً (تشتت مقبول)"
            else:
                conclusion = "مشتت (تفاوت كبير في المستويات)"

        gauss_data = {
            'x': [int(val) for val in discrete_x],
            'y': [float(val) for val in discrete_y],
            'actual': [float(val) for val in hist], # Density values of actual scores
            'mean': round(mean, 2),
            'std_dev': round(std, 2),
            'count': len(active_scores),
            'conclusion': conclusion
        }

    # Add level and class lists for the dynamic Gauss curve
    levels = list(Student.objects.exclude(academic_year__isnull=True).exclude(academic_year__exact='').values_list('academic_year', flat=True).distinct())

    classes_qs = Student.objects.exclude(class_name__isnull=True).exclude(class_name__exact='').values('academic_year', 'class_name').distinct()
    class_map = {}
    from .analytics_utils import format_class_name
    for item in classes_qs:
        lvl = item['academic_year'] or 'غير محدد'
        raw_cls = item['class_name']
        if raw_cls:
            cls = format_class_name(lvl, raw_cls)
            if lvl not in class_map:
                class_map[lvl] = []
            if cls not in class_map[lvl]:
                class_map[lvl].append(cls)

    # Get Dynamic Subjects List
    subjects_list = [s for s in Grade.objects.values_list('subject', flat=True).distinct() if s and not s.startswith('معدل')]
    subjects_list.sort()

    # Get Teachers List for Dropdown
    from .models import Employee
    teachers = Employee.objects.filter(rank='teacher').order_by('last_name')

    context = {
        'page_title': 'مختبر التحليل المتقدم',
        'gender_stats_json': json.dumps(gender_stats),
        'term_stats_json': json.dumps(term_stats),
        'class_stats_by_level_json': json.dumps(class_stats_by_level),
        'class_stats_by_level': class_stats_by_level,
        'advanced_stats': advanced_stats,
        'gauss_data_json': json.dumps(gauss_data),
        'levels': levels,
        'class_map_json': json.dumps(class_map),
        'teachers': teachers,
        'subjects_list': subjects_list,
        'selected_level': selected_level,
        'selected_class': selected_class,
        'selected_teacher_id': selected_teacher_id,
        'selected_subject': selected_subject
    }
    return render(request, 'students/advanced_analytics.html', context)

def statistical_tests_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or request.user.employeeprofile.has_perm('access_advanced_analytics')):
        return redirect('dashboard')

    levels = list(Student.objects.exclude(academic_year__isnull=True).exclude(academic_year__exact='').values_list('academic_year', flat=True).distinct())

    return render(request, 'students/statistical_tests.html', {'levels': levels})

def run_statistical_test(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    test_type = request.GET.get('test_type')
    grouping = request.GET.get('grouping')
    level = request.GET.get('level')

    from .models import Grade
    import pandas as pd
    import scipy.stats as stats

    grades_qs = Grade.objects.all()
    if level:
        import django.db.models as models
        # Also do a broad match for level just in case DB has 'أولى' but frontend passed 'أولى متوسط'
        grades_qs = grades_qs.filter(
            models.Q(student__academic_year=level) |
            models.Q(student__academic_year__icontains=level.replace(' متوسط', '').strip())
        )

    if not grades_qs.exists():
        return JsonResponse({'error': 'لا توجد بيانات كافية'})

    # We aggregate by student to get their general average for the test
    df = pd.DataFrame(list(grades_qs.values('student__id', 'student__gender', 'student__academic_year', 'student__class_name', 'score')))

    # Calculate mean score per student to avoid repeated measures bias in simple tests
    student_means = df.groupby(['student__id', 'student__gender', 'student__academic_year', 'student__class_name'])['score'].mean().reset_index()
    student_means = student_means[student_means['score'] > 0] # remove absences

    if student_means.empty:
        return JsonResponse({'error': 'لا توجد بيانات صحيحة بعد الفلترة'})

    group_col = 'student__' + grouping
    if group_col not in student_means.columns:
        return JsonResponse({'error': 'متغير التجميع غير صالح'})

    groups_data = {}
    arrays_for_test = []

    for name, group in student_means.groupby(group_col):
        # Ignore empty or None names
        if not str(name).strip() or str(name) == 'None': continue

        scores = group['score'].values
        if len(scores) > 1: # Need at least 2 for variance
            groups_data[str(name)] = {
                'count': len(scores),
                'mean': float(scores.mean()),
                'std': float(scores.std(ddof=1))
            }
            arrays_for_test.append(scores)

    if len(arrays_for_test) < 2:
        return JsonResponse({'error': 'لا توجد مجموعات كافية للمقارنة (تتطلب مجموعتين على الأقل)'})

    statistic = 0.0
    p_value = 1.0
    test_name = ""

    if test_type == 't_test_ind':
        if len(arrays_for_test) > 2:
            return JsonResponse({'error': 'اختبار T-Test يتطلب مجموعتين فقط. استخدم ANOVA.'})
        test_name = "Independent T-Test"
        statistic, p_value = stats.ttest_ind(arrays_for_test[0], arrays_for_test[1], equal_var=False)
    elif test_type == 'anova':
        test_name = "One-Way ANOVA"
        statistic, p_value = stats.f_oneway(*arrays_for_test)
    else:
        return JsonResponse({'error': 'نوع الاختبار غير معروف'})

    return JsonResponse({
        'test_name': test_name,
        'statistic': float(statistic),
        'p_value': float(p_value),
        'is_significant': bool(p_value < 0.05),
        'groups': groups_data
    })


def get_gauss_data(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    from .models import Grade
    import pandas as pd
    import numpy as np
    import scipy.stats as stats

    level = request.GET.get('level', '')
    class_name = request.GET.get('class_name', '')
    teacher_id = request.GET.get('teacher_id', '')
    subject = request.GET.get('subject', '')

    grades_qs = Grade.objects.all()

    # Subject Filtering
    if subject:
        import django.db.models as models
        grades_qs = grades_qs.filter(models.Q(subject__icontains=subject))

    # Teacher Assignment Filtering
    if teacher_id:
        from .models import Employee, TeacherAssignment
        try:
            teacher = Employee.objects.get(id=teacher_id)
            assignments = TeacherAssignment.objects.filter(teacher=teacher)
            teacher_classes = []
            teacher_subjects = []
            for assign in assignments:
                if assign.classes:
                    teacher_classes.extend(assign.classes)
                if assign.subject and assign.subject != '/' and assign.subject not in teacher_subjects:
                    teacher_subjects.append(assign.subject)

            teacher_classes = list(set(teacher_classes))

            if teacher_classes:
                import django.db.models as models
                q_classes = models.Q()
                from .analytics_utils import unformat_class_name
                for cls in teacher_classes:
                    raw_c = unformat_class_name(cls)
                    if raw_c and raw_c.isdigit():
                        q_classes |= models.Q(student__class_name=cls) | models.Q(student__class_name=raw_c) | models.Q(student__class_name__endswith=f" {raw_c}") | models.Q(student__class_name__endswith=f"م{raw_c}") | models.Q(student__class_name__icontains=raw_c)
                    else:
                        q_classes |= models.Q(student__class_name=cls)
                grades_qs = grades_qs.filter(q_classes)

            if teacher_subjects and not subject:
                q_subjs = models.Q()
                for subj in teacher_subjects:
                    q_subjs |= models.Q(subject__icontains=subj)
                grades_qs = grades_qs.filter(q_subjs)

        except Employee.DoesNotExist:
            pass
    else:
        if level:
            import django.db.models as models
            grades_qs = grades_qs.filter(
                models.Q(student__academic_year=level) |
                models.Q(student__academic_year__icontains=level.replace(' متوسط', '').strip())
            )
        if class_name:
            from .analytics_utils import unformat_class_name
            import django.db.models as models
            # DB might have '5', '1م5', or 'أولى متوسط 5' or 'أولى 5'.
            # We extract the pure digit (e.g. '5') and match any class name ending with or containing that digit for that level
            raw_class = unformat_class_name(class_name)
            if raw_class and raw_class.isdigit():
                grades_qs = grades_qs.filter(
                    models.Q(student__class_name=class_name) |
                    models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__endswith=f"م{raw_class}") |
                    models.Q(student__class_name__icontains=raw_class)
                )
            else:
                grades_qs = grades_qs.filter(student__class_name=class_name)

    if not grades_qs.exists():
        return JsonResponse({'x': [], 'y': [], 'actual': [], 'mean': 0, 'std_dev': 0, 'count': 0})

    df = pd.DataFrame(list(grades_qs.values('student__id', 'subject', 'student__class_name', 'student__academic_year', 'term', 'score')))

    if subject or teacher_id:
        # If analyzing a specific subject or teacher, we don't look at the 'general average'
        # We look directly at the scores of that subject
        # If multiple subjects are caught (e.g., if a teacher teaches Math and Physics), we average them per student or treat them as raw scores
        # We'll treat them as raw scores per student per subject
        # To avoid multiple scores for the same student skewing the count, we group by student
        target_df = df.groupby(['student__id'])['score'].mean().reset_index()
    else:
        general_avg_subjs = [subj for subj in df['subject'].unique() if subj and isinstance(subj, str) and (subj.strip() == 'المعدل العام' or subj.strip().startswith('معدل الفصل'))]

        if general_avg_subjs:
            target_df = df[df['subject'].isin(general_avg_subjs)].copy()
        else:
            target_df = df.groupby(['student__id', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()

    active_scores = target_df[target_df['score'] > 0]['score'].dropna()
    active_scores = active_scores.clip(upper=20.0)

    if len(active_scores) <= 1:
        return JsonResponse({'x': [], 'y': [], 'actual': [], 'mean': 0, 'std_dev': 0, 'count': len(active_scores)})

    mean = active_scores.mean()
    std = active_scores.std()

    bins = np.arange(0, 22, 1)
    hist, _ = np.histogram(active_scores, bins=bins, density=True)

    discrete_x = np.arange(0, 21, 1)
    discrete_y = stats.norm.pdf(discrete_x, mean, std) if std > 0 else np.zeros_like(discrete_x)

    conclusion = "غير محدد"
    if not pd.isna(std) and not pd.isna(mean):
        if std < 1.5:
            conclusion = "متجانس جداً (متقارب)"
        elif std < 2.5:
            conclusion = "متجانس (توزيع طبيعي)"
        elif std < 3.5:
            conclusion = "متجانس قليلاً (تشتت مقبول)"
        else:
            conclusion = "مشتت (تفاوت كبير في المستويات)"

    gauss_data = {
        'x': [int(val) for val in discrete_x],
        'y': [float(val) for val in discrete_y],
        'actual': [float(val) for val in hist],
        'mean': round(mean, 2) if not pd.isna(mean) else 0,
        'std_dev': round(std, 2) if not pd.isna(std) else 0,
        'count': int(len(active_scores)),
        'median': round(active_scores.median(), 2) if not active_scores.empty else 0,
        'mode': round(active_scores.mode()[0], 2) if not active_scores.empty and not active_scores.mode().empty else 0,
        'variance': round(active_scores.var(), 2) if len(active_scores) > 1 else 0,
        'range': round(active_scores.max() - active_scores.min(), 2) if not active_scores.empty else 0,
        'min': round(active_scores.min(), 2) if not active_scores.empty else 0,
        'max': round(active_scores.max(), 2) if not active_scores.empty else 0,
        'conclusion': conclusion
    }
    return JsonResponse(gauss_data)

def upload_grades_ajax(request):
    """Handles bulk uploading of multiple grade files with AJAX progress"""
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        term = request.POST.get('term')
        import_mode = request.POST.get('import_mode', 'local')

        import tempfile
        import os
        from .grade_importer import process_grades_file, process_grades_file_ai

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            if import_mode == 'ai':
                count, msg = process_grades_file_ai(temp_path, term)
            else:
                count, msg = process_grades_file(temp_path, term)

            success = count > 0
            return JsonResponse({'success': success, 'message': msg, 'count': count})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"خطأ: {str(e)}", 'count': 0})
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    return JsonResponse({'success': False, 'message': 'طلب غير صالح'})
