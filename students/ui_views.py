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

    update_existing = request.POST.get('update_existing') == 'on'

    if request.method == 'POST' and request.FILES.get('eleve_file'):
        eleve_file = request.FILES['eleve_file']
        temp_path = None

        try:
            _, ext = os.path.splitext(eleve_file.name)
            if not ext: ext = '.xls'

            # Save file safely
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in eleve_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            # 1. Parse File using Robust Logic
            raw_data = parse_student_file(temp_path)

            if not raw_data:
                messages.error(request, "لم يتم العثور على بيانات صالحة في الملف.")
            else:
                # 2. Create Dataset for django-import-export
                # Get headers from first row keys
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
                    msg_type = messages.success if total_processed > 0 else messages.warning

                    msg_type(request, f"تمت المعالجة: {total_processed} سجل. (جديد: {new_count}، تحديث: {update_count}، تم تخطي: {skip_count}). تحقق من سجلات التتبع إذا كان العدد أقل من المتوقع.")

        except Exception as e:
            messages.error(request, f"خطأ في الملف أو المعالجة: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

        return redirect('settings')

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
from .ai_utils import analyze_assignment_document

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
                    # Parse Rank
                    rank_str = emp.get('rank', 'worker')
                    rank_map = {'أستاذ': 'teacher', 'عامل': 'worker', 'إداري': 'admin', 'مستشار': 'admin', 'مقتصد': 'admin'}
                    rank = 'worker'
                    for key, val in rank_map.items():
                        if key in rank_str:
                            rank = val
                            break

                    # Handle Subject
                    subject = emp.get('subject', '/')
                    if rank != 'teacher':
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

                    Employee.objects.update_or_create(
                        employee_code=emp.get('employee_code'),
                        defaults={
                            'last_name': emp.get('last_name', ''),
                            'first_name': emp.get('first_name', ''),
                            'full_name': f"{emp.get('last_name', '')} {emp.get('first_name', '')}",
                            'date_of_birth': dob,
                            'rank': rank,
                            'subject': subject,
                            'grade': emp.get('grade', ''),
                            'effective_date': eff_date,
                            'phone': emp.get('phone', ''),
                            'email': emp.get('email', ''),
                            'role': rank
                        }
                    )
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
                data = {
                    'employee_code': request.POST.get('employee_code'),
                    'last_name': request.POST.get('last_name'),
                    'first_name': request.POST.get('first_name'),
                    'full_name': f"{request.POST.get('last_name')} {request.POST.get('first_name')}",
                    'rank': request.POST.get('rank'),
                    'subject': request.POST.get('subject') if request.POST.get('rank') == 'teacher' else '/',
                    'grade': request.POST.get('grade'),
                    'phone': request.POST.get('phone'),
                    'email': request.POST.get('email'),
                    'date_of_birth': request.POST.get('date_of_birth') or None,
                    'effective_date': request.POST.get('effective_date') or None,
                    'role': request.POST.get('rank')
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

        elif action == 'import_assignment_global':
            file = request.FILES.get('assignment_file')
            if file:
                try:
                    # Save temporary file for analysis
                    from .ai_utils import analyze_global_assignment

                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                        for chunk in file.chunks():
                            tmp.write(chunk)
                        tmp_path = tmp.name

                    results = analyze_global_assignment(tmp_path)

                    if results['processed'] > 0:
                        messages.success(request, f"تم تحليل الإسناد: تم تحديث {results['processed']} أستاذ (تم العثور على {results['classes']} قسم).")
                    else:
                        messages.warning(request, "لم يتم العثور على بيانات مطابقة. تأكد من أن أسماء الأساتذة في الملف تطابق قاعدة البيانات.")

                    os.remove(tmp_path)
                except Exception as e:
                    messages.error(request, f"خطأ في التحليل: {e}")
            return redirect('hr_home')

    # Filtering
    rank_filter = request.GET.get('rank')
    employees = Employee.objects.all().order_by('last_name')
    if rank_filter:
        employees = employees.filter(rank=rank_filter)

    context = {
        'employees': employees,
        'current_rank': rank_filter,
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
            prompt = f"اقترح خطوات ومحاور لاستبيان حول الموضوع: {topic}. الجمهور المستهدف: {target}. قدم إجابة مهيكلة في شكل خطوات."
            ai_suggestion = ai.generate_response("أنت مستشار توجيه مدرسي خبير.", prompt, rag_enabled=False)

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
        free_mode = request.POST.get('free_mode') == 'true'

        ai = AIService()
        # In chat mode, we treat system instruction as generic or manager context depending on mode
        sys_instr = "أنت مساعد مدير المدرسة."

        response_text = ai.generate_response(sys_instr, query, rag_enabled=not free_mode, free_mode=free_mode)
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
