from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings, Employee, SystemMessage, Survey, PendingUpdate, Task, TeacherObservation, SchoolMemory, UserRole
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
from django.db.models import Q

def pending_updates_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and request.user.profile.role != 'director' and not request.user.is_superuser:
        return redirect('dashboard')

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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('manage_settings'):
         return redirect('dashboard')

    context = {
        'total_students': Student.objects.count(),
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/settings.html', context)

def import_eleve_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
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

            # Check for Manual Mapping Request OR Preview Logic
            if force_manual:
                # Preview Mode
                from .import_utils import extract_rows_from_file, detect_headers
                # Re-open safely
                with open(temp_path, 'rb') as f:
                    all_rows = list(extract_rows_from_file(f))

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
                # 2. Create Dataset for django-import-export
                headers = list(raw_data[0].keys())
                dataset = Dataset(headers=headers)

                for row in raw_data:
                    dataset.append([row[h] for h in headers])

                # 3. Use Resource to Import
                resource = StudentResource()
                result = resource.import_data(dataset, dry_run=False, raise_errors=True)

                if result.has_errors():
                    messages.error(request, "حدثت أخطاء أثناء الاستيراد.")
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
    if not request.user.is_authenticated: return redirect('canteen_landing')

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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_canteen'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/canteen.html', context)

def student_list(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_management'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/management.html', context)

def library_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_library'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/library.html', context)

def archive_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_archive'):
        return redirect('dashboard')
    context = {
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/archive.html', context)

def print_student_cards(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
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

from .models import TeacherAssignment
from .ai_utils import analyze_assignment_document, analyze_global_assignment_content
import difflib

def assignment_matching_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')

    # 1. Processing Uploaded File (GET)
    if request.method == 'GET':
        temp_path = request.session.get('assignment_temp_path')
        if not temp_path or not os.path.exists(temp_path):
            messages.error(request, "انتهت صلاحية الجلسة أو الملف غير موجود.")
            return redirect('hr_home')

        try:
            candidates = analyze_global_assignment_content(temp_path)
            all_teachers = Employee.objects.filter(rank='teacher').order_by('last_name')

            # Improved Fuzzy Matching
            def get_similarity(s1, s2):
                if not s1 or not s2: return 0.0
                return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

            for c in candidates:
                best_score = 0.0
                best_match = None
                c_norm = c['name'].strip()

                for t in all_teachers:
                    # Construct full names
                    t_full = f"{t.last_name} {t.first_name}"
                    t_rev = f"{t.first_name} {t.last_name}" # Handle reversed order

                    # 1. Direct Containment (Highest Confidence)
                    if t.last_name in c_norm and t.first_name in c_norm:
                        score = 1.0

                    # 2. Last Name Only (High Confidence if uncommon)
                    elif t.last_name in c_norm and len(t.last_name) > 3:
                        score = 0.8

                    # 3. Fuzzy Ratio on Full String
                    else:
                        score = max(
                            get_similarity(c_norm, t_full),
                            get_similarity(c_norm, t_rev),
                            get_similarity(c_norm, t.last_name) # Fallback to surname similarity
                        )

                    if score > best_score:
                        best_score = score
                        best_match = t

                # Threshold: 0.6 is usually good for fuzzy names with typos
                if best_score >= 0.6 and best_match:
                    c['suggested_id'] = best_match.id

                import json
                c['classes_json'] = json.dumps(c['classes'])

            context = {
                'candidates': candidates,
                'all_teachers': all_teachers,
                'temp_file_path': temp_path,
                'unmatched_count': len(candidates)
            }
            return render(request, 'students/assignment_match.html', context)

        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            return redirect('hr_home')

    # 2. Saving Matches (POST)
    elif request.method == 'POST':
        try:
            import json
            count = 0

            # Iterate through form fields
            for key, value in request.POST.items():
                if key.startswith('match_'):
                    idx = key.split('_')[1]
                    action = value # 'ignore', 'create_new', or ID

                    if action == 'ignore': continue

                    name = request.POST.get(f'name_{idx}')
                    subject = request.POST.get(f'subject_{idx}')
                    classes_json = request.POST.get(f'classes_{idx}')
                    classes = json.loads(classes_json) if classes_json else []

                    teacher = None
                    if action == 'create_new':
                        # Create minimal teacher record
                        parts = name.split()
                        ln = parts[0] if parts else "Unknown"
                        fn = " ".join(parts[1:]) if len(parts) > 1 else ""
                        teacher = Employee.objects.create(
                            last_name=ln, first_name=fn,
                            full_name=name, rank='teacher', subject=subject
                        )
                    else:
                        # Existing ID
                        teacher = Employee.objects.get(id=action)
                        if subject and subject != '/':
                            teacher.subject = subject
                            teacher.save()

                    # Save Assignment
                    TeacherAssignment.objects.create(
                        teacher=teacher,
                        subject=subject or teacher.subject or "عام",
                        classes=classes
                    )
                    count += 1

            messages.success(request, f"تم حفظ الإسناد لـ {count} أستاذ.")

            # Clean up temp file
            temp_path = request.POST.get('file_path')
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

            # Clear session
            if 'assignment_temp_path' in request.session:
                del request.session['assignment_temp_path']

        except Exception as e:
            messages.error(request, f"خطأ في الحفظ: {e}")

        return redirect('hr_home')

def hr_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
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
                        'full_name': f"{ln} {fn}",
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
                    'full_name': f"{request.POST.get('last_name')} {request.POST.get('first_name')}",
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
                subject = request.POST.get('subject')
                classes_str = request.POST.get('classes_str')

                # Parse classes: split by comma or space
                raw_list = classes_str.replace(',', ' ').split()
                classes_list = [c.strip() for c in raw_list if c.strip()]

                teacher = Employee.objects.get(id=teacher_id)
                if subject:
                    teacher.subject = subject
                    teacher.save()

                # Update or Create Assignment
                assign, created = TeacherAssignment.objects.get_or_create(teacher=teacher)
                assign.subject = subject or teacher.subject or "عام"
                assign.classes = classes_list
                assign.save()

                messages.success(request, f"تم تحديث الإسناد للأستاذ {teacher.last_name}")
            except Exception as e:
                messages.error(request, f"خطأ: {e}")
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

                    # Store path in session to pass to matching view
                    request.session['assignment_temp_path'] = tmp_path
                    return redirect('assignment_matching_view')

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

    context = {
        'employees': employees,
        'current_rank': rank_filter,
        'counts': counts,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/hr.html', context)

def hr_delete(request, pk):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    get_object_or_404(Employee, pk=pk).delete()
    messages.success(request, "تم الحذف")
    return redirect('hr_home')

def parents_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_guidance'):
        return redirect('dashboard')

    ai_suggestion = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ai_suggest':
            topic = request.POST.get('topic')
            target = request.POST.get('target_audience')
            from .ai_utils import AIService
            ai = AIService()

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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and request.user.profile.role != 'director' and not request.user.is_superuser:
        return redirect('dashboard')

    return render(request, 'students/ai_manual.html')

def ai_chat_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and request.user.profile.role != 'director' and not request.user.is_superuser:
        return redirect('dashboard')

    if request.method == 'POST':
        from .ai_utils import AIService
        from django.http import JsonResponse

        query = request.POST.get('query')
        # Mode requested by UI (will be checked against permissions inside AIService)
        requested_mode = request.POST.get('mode', None)

        # Pass current user for permission check
        ai = AIService(user=request.user)

        # System instructions base (overridden by mode logic in generate_response)
        sys_instr = "أنت مساعد مدير المدرسة."

        rag_enabled = (requested_mode == 'rag' or requested_mode is None)

        response_text = ai.generate_response(sys_instr, query, rag_enabled=rag_enabled, mode=requested_mode)
        return JsonResponse({'response': response_text})

    return render(request, 'students/ai_chat.html')

# --- AI & Task UI Views ---

def tasks_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')

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
    if not request.user.is_authenticated: return redirect('canteen_landing')
    is_director = request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser

    if not is_director: return redirect('dashboard')

    context = {
        'is_director': True,
        'memories': SchoolMemory.objects.all().order_by('-created_at')
    }
    return render(request, 'students/ai_control.html', context)

def observations_view(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')

    is_director = request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser

    context = {
        'is_director': is_director,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
    }
    return render(request, 'students/observations.html', context)
