from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponse
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


def _count_nav_surfaces(profile):
    """عدد الواجهات الرئيسية المفتوحة للمستخدم (لتجنب إعادة التوجيه لواجهة واحدة فقط)."""
    keys = [
        'access_canteen', 'access_library', 'access_management', 'access_archive',
        'access_guidance', 'access_hr', 'access_parents',
    ]
    n = sum(1 for k in keys if profile.has_perm(k))
    if profile.has_perm('access_analytics') or profile.has_perm('access_advanced_analytics'):
        n += 1
    return n


def unregister_sw_view(request):
    """صفحة طوارئ: إلغاء تسجيل Service Worker. المسار يحتوي /api/ فلا يعترضه الـ SW القديم."""
    html = '''<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><title>إلغاء Service Worker</title></head><body style="font-family: Cairo; padding: 2rem; text-align: center;">
    <p id="msg">جاري إلغاء تسجيل Service Worker...</p>
    <script>
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.getRegistrations().then(function(regs) {
            var p = Promise.all(regs.map(function(r) { return r.unregister(); }));
            p.then(function() {
                document.getElementById("msg").innerHTML = "تم إلغاء التسجيل. <a href='/'>العودة للصفحة الرئيسية</a>";
                setTimeout(function(){ location.href = "/"; }, 1500);
            });
        });
    } else {
        document.getElementById("msg").innerHTML = "لا يوجد Service Worker. <a href='/'>العودة</a>";
    }
    </script></body></html>'''
    return HttpResponse(html, content_type='text/html; charset=utf-8')

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
    prof = getattr(request.user, 'profile', None)
    if not request.user.is_superuser and not (prof and prof.role == 'director'):
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
            else:
                # إعادة توجيه تلقائية فقط عندما تكون واجهة رئيسية واحدة؛ وإلا يبقى لوحة القيادة والشريط الجانبي.
                if _count_nav_surfaces(profile) == 1:
                    if profile.has_perm('access_canteen'): return redirect('canteen_home')
                    elif profile.has_perm('access_library'): return redirect('library_home')
                    elif profile.has_perm('access_management'): return redirect('students_management')
                    elif profile.has_perm('access_archive'): return redirect('archive_home')
                    elif profile.has_perm('access_guidance'): return redirect('guidance_home')
                    elif profile.has_perm('access_hr'): return redirect('hr_home')
                    elif profile.has_perm('access_parents'): return redirect('parents_home')
                    elif profile.has_perm('access_analytics') or profile.has_perm('access_advanced_analytics'): return redirect('analytics_dashboard')
                else:
                    pass
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

    total_students = Student.objects.count()
    half_board_count = Student.objects.filter(attendance_system='نصف داخلي').count()
    ext_board_count = total_students - half_board_count

    openrouter_balance = None
    openrouter_balance_info = None
    try:
        from students.ai_utils import AIService
        ai = AIService()
        openrouter_balance_info = ai.get_openrouter_balance_info()
        openrouter_balance = openrouter_balance_info.get('balance') if isinstance(openrouter_balance_info, dict) else None
    except Exception as e:
        # لا نكتم الخطأ حتى يظهر السبب في لوحة القيادة بدل N/A الغامضة
        openrouter_balance_info = {'ok': False, 'balance': None, 'message': f'خطأ داخلي: {e}', 'key_present': False}
    context = {
        'total_students': total_students,
        'half_board_count': half_board_count,
        'ext_board_count': ext_board_count,
        'db_status': 'متصل',
        'present_today': CanteenAttendance.objects.filter(date=date.today()).count(),
        'absent_today': half_board_count - CanteenAttendance.objects.filter(date=date.today()).count(),
        'detailed_stats': detailed_stats,
        'assigned_students': assigned_students,
        'teacher_classes': teacher_classes,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser,
        'openrouter_balance': openrouter_balance,
        'openrouter_balance_info': openrouter_balance_info,
    }
    return render(request, 'students/dashboard.html', context)


def api_openrouter_balance(request):
    """API: إرجاع رصيد OpenRouter مع تشخيص. (Director only)"""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'balance': None, 'message': 'Unauthorized'}, status=403)
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'director')):
        return JsonResponse({'ok': False, 'balance': None, 'message': 'Forbidden'}, status=403)
    try:
        from students.ai_utils import AIService
        info = AIService(user=request.user).get_openrouter_balance_info()
        return JsonResponse(info if isinstance(info, dict) else {'ok': False, 'balance': None, 'message': 'Unknown response'})
    except Exception as e:
        return JsonResponse({'ok': False, 'balance': None, 'message': f'Error: {e}'}, status=500)

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
    from .school_year_utils import get_current_school_year
    academic_year = get_current_school_year()

    context = {
        'students': students,
        'school_name': school_name,
        'academic_year': academic_year
    }
    return render(request, 'students/print_cards.html', context)

# --- New Modules ---

from .models import TeacherAssignment, ClassAlias, Student, Employee
from .ai_utils import analyze_assignment_document, analyze_global_assignment_content
import difflib

def sync_ta_to_analytics(teacher):
    """Keep analytics_assignments in sync with TeacherAssignment so both sources show same data."""
    if not teacher or not isinstance(teacher, Employee):
        return
    tas = TeacherAssignment.objects.filter(teacher=teacher)
    data = [{'subject': ta.subject, 'classes': list(ta.classes or [])} for ta in tas]
    teacher.analytics_assignments = data
    teacher.save(update_fields=['analytics_assignments'])


def _norm_subj_analytics(t):
    if not t:
        return ''
    t = str(t).strip().replace('ـ', '').replace('  ', ' ')
    if t.startswith('ال'):
        t = t[2:].strip()
    return t.lower()


def _subject_matches_analytics(s1, s2):
    n1, n2 = _norm_subj_analytics(s1), _norm_subj_analytics(s2)
    return n1 == n2 or n1 in n2 or n2 in n1 or (s1 and s2 and (s1 in s2 or s2 in s1))


def sync_all_analytics_assignments_from_hr():
    """
    ملء إسناد التحليل من الموارد البشرية لجميع الأساتذة (نفس منطق الأمر sync_analytics_assignments_from_hr).
    يُستدعى تلقائياً عند فتح صفحة التحليل حتى لا يلزم استيراد الإسناد يدوياً.
    """
    teachers = Employee.objects.filter(rank='teacher')
    for emp in teachers:
        hr_assignments = list(
            TeacherAssignment.objects.filter(teacher=emp).values_list('subject', 'classes')
        )
        if not hr_assignments:
            continue
        current = list(emp.analytics_assignments or [])
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
            current = [{'subject': s, 'classes': list(cl)} for s, cl in hr_by_subj.items()]
            changed = True
        else:
            for a in current:
                subj = (a.get('subject') or '').strip()
                cl = a.get('classes')
                if not subj:
                    continue
                if cl and isinstance(cl, list) and len(cl) > 0:
                    continue
                for hr_subj, hr_cl in hr_by_subj.items():
                    if _subject_matches_analytics(subj, hr_subj):
                        a['classes'] = list(hr_cl)
                        changed = True
                        break
        if changed:
            emp.analytics_assignments = current
            emp.save(update_fields=['analytics_assignments'])

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
            # Group by teacher: same teacher may appear in multiple rows (e.g. two subjects)
            teacher_aggregate = {}  # teacher_id or ('create_new', final_name) -> { teacher_obj, assignments[], main_subject }
            for idx, c in enumerate(candidates):
                action = request.POST.get(f'match_{idx}')
                if action == 'ignore':
                    continue

                final_name = request.POST.get(f'name_{idx}', c['name'])
                subjects = request.POST.getlist(f'subject_{idx}[]')
                block_indices = request.POST.getlist(f'block_indices_{idx}[]')

                assignments = []
                for j, subject in enumerate(subjects):
                    if subject.strip() and j < len(block_indices):
                        block_idx = block_indices[j]
                        classes_checked = request.POST.getlist(f'classes_{idx}_{block_idx}[]')
                        assignments.append({
                            'subject': subject.strip(),
                            'classes': classes_checked
                        })

                main_subject = subjects[0].strip() if subjects else c['subject']
                key = ('create_new', final_name) if action == 'create_new' else int(action)

                if key not in teacher_aggregate:
                    teacher_aggregate[key] = {'assignments': [], 'main_subject': main_subject, 'final_name': final_name}
                teacher_aggregate[key]['assignments'].extend(assignments)
                if main_subject and main_subject != '/':
                    teacher_aggregate[key]['main_subject'] = main_subject

            count = 0
            saved_teacher_ids = []
            for key, agg in teacher_aggregate.items():
                action = key if not isinstance(key, tuple) else 'create_new'
                final_name = agg['final_name'] if isinstance(key, tuple) else None
                assignments = [a for a in agg['assignments'] if a.get('subject')]
                main_subject = agg['main_subject']

                teacher = None
                if action == 'create_new':
                    parts = (final_name or '').split()
                    ln = parts[0] if parts else "غير معروف"
                    fn = " ".join(parts[1:]) if len(parts) > 1 else ""
                    teacher = Employee.objects.create(
                        last_name=ln, first_name=fn,
                        rank='teacher', subject=main_subject or '/'
                    )
                else:
                    try:
                        teacher = Employee.objects.get(id=action)
                        if main_subject and main_subject != '/':
                            teacher.subject = main_subject
                            teacher.save()
                        TeacherAssignment.objects.filter(teacher=teacher).delete()
                    except Employee.DoesNotExist:
                        continue

                if teacher:
                    for assignment in assignments:
                        TeacherAssignment.objects.create(
                            teacher=teacher,
                            subject=assignment['subject'],
                            classes=assignment.get('classes', [])
                        )
                    teacher.refresh_from_db()
                    sync_ta_to_analytics(teacher)
                    count += 1
                    saved_teacher_ids.append(str(teacher.id))

            messages.success(request, f"تم حفظ الإسناد لـ {count} أستاذ وربطهم بنجاح.")
            if 'ai_extracted_data' in request.session:
                del request.session['ai_extracted_data']
            from django.urls import reverse
            import time
            order_param = '&order=' + ','.join(saved_teacher_ids) if saved_teacher_ids else ''
            return redirect(f"{reverse('hr_home')}?_r={int(time.time())}{order_param}")

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
            c_parts = [p.strip() for p in re.split(r'[\s\u064b-\u0652]+', c_norm) if len(p.strip()) > 1]

            for t in all_teachers:
                t_ln = (t.last_name or '').strip()
                t_fn = (t.first_name or '').strip()

                t_full = f"{t_ln} {t_fn}".strip()
                t_rev = f"{t_fn} {t_ln}".strip()

                # التطابق بين اللقب والاسم: لا نقبل اقتراح أستاذ إلا إذا ظهر كل من اللقب والاسم في النص
                if t_ln and t_fn and t_ln in c_norm and t_fn in c_norm:
                    score = 1.0
                elif t_ln and t_fn and t_ln in c_norm and t_fn not in c_norm:
                    # نفس اللقب لكن اسم مختلف (مثل طرافي امباركة vs أرفيس امباركة) — لا نطابق
                    score = 0.35
                elif t_ln and t_ln in c_norm and len(t_ln) > 3 and not t_fn:
                    score = 0.8
                elif t_ln and t_ln in c_norm and len(t_ln) > 3:
                    score = 0.5
                else:
                    score = max(
                        get_similarity(c_norm, t_full),
                        get_similarity(c_norm, t_rev),
                        get_similarity(c_norm, t_ln)
                    )

                # عندما يتشارك أساتذة نفس اللقب، نعتمد الجزء المميز (الاسم الأول)
                if c_parts and t_ln and t_fn and score >= 0.4:
                    last_part = c_parts[-1] if c_parts else ''
                    first_part = c_parts[0] if c_parts else ''
                    if last_part and len(last_part) > 2:
                        if (t_ln in last_part or last_part in t_ln) and (t_fn in first_part or first_part in t_fn or t_fn in c_norm):
                            score = max(score, 0.95)
                        elif (t_ln in last_part or last_part in t_ln) and (first_part not in t_fn and t_fn not in first_part and t_fn not in c_norm):
                            score = min(score, 0.4)

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

def get_all_hr_assignments_api(request):
    """Returns HR assignments for all teachers (for quick edit, always fresh from DB)."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'غير مصرح'})
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return JsonResponse({'status': 'error', 'message': 'ليس لديك صلاحية'})
    from .models import Employee
    order_str = request.GET.get('order', '')
    order_ids = [x.strip() for x in order_str.split(',') if x.strip()] if order_str else None

    teachers = Employee.objects.filter(rank='teacher')
    data = {}
    for emp in teachers:
        assignments = list(emp.assignments.all().values('subject', 'classes'))
        data[str(emp.id)] = {
            'name': f"{emp.last_name or ''} {emp.first_name or ''}".strip(),
            'assignments': assignments
        }
    result = {'status': 'success', 'teachers': data}
    if order_ids:
        result['order'] = [i for i in order_ids if i in data]
    return JsonResponse(result)


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
                import re
                employees_data = parse_hr_file(temp_path)

                from django.db import transaction
                count = 0
                skipped_no_code = 0

                with transaction.atomic():
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

                        # شرط منع التكرار: الرمز الوظيفي مطلوب في الاستيراد (إلا اليدوي)
                        emp_code = (emp.get('employee_code') or '').strip()
                        if not emp_code or len(emp_code) < 4:
                            skipped_no_code += 1
                            continue
                        ln = (emp.get('last_name') or '').strip()
                        fn = (emp.get('first_name') or '').strip()

                        def _norm(s):
                            if not s: return ''
                            s = str(s).strip().replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
                            s = s.replace('ة', 'ه').replace('ى', 'ي').replace('ئ', 'ي').replace('ؤ', 'و').replace('ء', '')
                            s = re.sub(r'(^|\s)اع', r'\1ع', s)
                            return s

                        # Skip auto-generated codes (e.g. بنزفايزة123) for matching
                        is_auto_code = bool(emp_code and re.match(r'^[^\d]+\d+$', str(emp_code)) and len(emp_code) < 20)

                        existing = None
                        if emp_code and not is_auto_code:
                            existing = Employee.objects.filter(employee_code=emp_code).first()

                        if not existing and ln and fn:
                            existing = Employee.objects.filter(
                                last_name=ln, first_name=fn, date_of_birth=dob
                            ).first()
                        if not existing and ln and fn:
                            existing = Employee.objects.filter(
                                last_name=ln, first_name=fn
                            ).first()
                        if not existing and ln and fn:
                            ln_n, fn_n = _norm(ln), _norm(fn)
                            for e in Employee.objects.filter(rank=sys_rank):
                                if _norm(e.last_name or '') == ln_n and _norm(e.first_name or '') == fn_n:
                                    existing = e
                                    break

                        defaults = {
                            'last_name': ln, 'first_name': fn, 'date_of_birth': dob,
                            'rank': sys_rank, 'role': raw_rank, 'subject': subject,
                            'grade': emp.get('grade', ''), 'effective_date': eff_date,
                            'phone': emp.get('phone', ''), 'email': emp.get('email', ''),
                        }

                        if existing:
                            for key, value in defaults.items():
                                setattr(existing, key, value)
                            if is_auto_code and existing.employee_code:
                                pass
                            elif emp_code and not is_auto_code:
                                existing.employee_code = emp_code
                            existing.save()
                        else:
                            Employee.objects.create(employee_code=emp_code or None, **defaults)

                        count += 1

                msg = f"تم استيراد/تحديث {count} موظف."
                if skipped_no_code:
                    msg += f" (تم تخطي {skipped_no_code} صفاً لعدم وجود رمز وظيفي صالح)"
                messages.success(request, msg)
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
                    'employee_code': (request.POST.get('employee_code') or '').strip() or None,
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
            from django.db import transaction
            try:
                teacher_id = request.POST.get('teacher_id')
                payload = request.POST.get('assignments_payload')

                teacher = Employee.objects.get(id=teacher_id)

                with transaction.atomic():
                    TeacherAssignment.objects.filter(teacher=teacher).delete()

                    assignments = []
                    if payload:
                        import json
                        try:
                            assignments = json.loads(payload)
                        except:
                            pass

                    main_subject = ''
                    new_assignments = []
                    for assign in assignments:
                        subj = assign.get('subject', '').strip()
                        if subj:
                            if not main_subject: main_subject = subj
                            new_assignments.append(
                                TeacherAssignment(
                                    teacher=teacher,
                                    subject=subj,
                                    classes=assign.get('classes', [])
                                )
                            )

                    if new_assignments:
                        TeacherAssignment.objects.bulk_create(new_assignments)

                    if main_subject:
                        teacher.subject = main_subject
                        teacher.save(update_fields=['subject'])

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
    teacher_order = request.GET.get('order', '')  # comma-separated IDs from assignment import

    context = {
        'employees': employees,
        'current_rank': rank_filter,
        'counts': counts,
        'all_classes': all_classes,
        'auto_select_data': auto_select_data,
        'teacher_order': teacher_order,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/hr.html', context)

def hr_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('accept', '').startswith('application/json')

    try:
        emp = Employee.objects.get(pk=pk)
        emp.delete()
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم الحذف'})
        messages.success(request, "تم الحذف")
    except Employee.DoesNotExist:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'هذا الموظف غير موجود أو تم حذفه مسبقاً.'})
        messages.warning(request, "هذا الموظف غير موجود أو تم حذفه مسبقاً.")

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
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_ai_chat')):
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
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_tasks')):
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
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_ai_control')):
        return redirect('dashboard')

    context = {
        'is_director': True,
        'memories': SchoolMemory.objects.all().order_by('-created_at')
    }
    return render(request, 'students/ai_control.html', context)


def analytics_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_analytics')):
        return redirect('dashboard')

    # مزامنة إسناد التحليل من الموارد البشرية تلقائياً مرة واحدة لكل جلسة عند فتح التحليل
    if request.method == 'GET' and not request.session.get('analytics_hr_synced'):
        try:
            sync_all_analytics_assignments_from_hr()
            request.session['analytics_hr_synced'] = True
        except Exception:
            pass

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'import_grades' and request.FILES.get('file'):
            if not (
                request.user.is_superuser
                or (hasattr(request.user, 'profile') and request.user.profile.role == 'director')
                or (hasattr(request.user, 'profile') and request.user.profile.has_perm('import_grades'))
            ):
                messages.error(request, 'لا تملك صلاحية استيراد العلامات.')
                return redirect('analytics_dashboard')
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

    teacher_subjects = []
    teacher_classes = []

    # Get distinct academic years (levels) and classes - prefer class_code for consistency
    levels = list(Student.objects.values_list('academic_year', flat=True).distinct())
    levels = [lvl for lvl in levels if lvl]

    classes_qs = Student.objects.values('academic_year', 'class_name', 'class_code').distinct()
    class_map = {}
    from .analytics_utils import format_class_name
    for item in classes_qs:
        lvl = item['academic_year'] or 'غير محدد'
        raw_cls = item['class_name']
        code = item.get('class_code')
        cls = (code if code else format_class_name(lvl, raw_cls))
        if raw_cls or cls:
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

    def _normalize(s):
        import re
        return re.sub(r'\s+', ' ', str(s).strip()).strip() if s else ''

    def _strip_list(lst):
        return [_normalize(str(x)) for x in lst if x is not None and _normalize(str(x))]

    selected_terms = _strip_list(request.GET.getlist('term'))
    selected_levels = _strip_list(request.GET.getlist('level'))
    selected_classes = _strip_list(request.GET.getlist('class_name'))
    selected_teacher_ids = _strip_list(request.GET.getlist('teacher_id'))
    selected_subjects = _strip_list(request.GET.getlist('subject'))
    filter_applied = request.GET.get('filter_applied', '')
    # توافق رجعي: دعم القيم المفردة من الروابط القديمة
    if not selected_terms and request.GET.get('term'):
        v = str(request.GET.get('term', '')).strip()
        if v:
            selected_terms = [v]
    if not selected_levels and request.GET.get('level'):
        v = str(request.GET.get('level', '')).strip()
        if v:
            selected_levels = [v]
    if not selected_teacher_ids and request.GET.get('teacher_id'):
        v = str(request.GET.get('teacher_id', '')).strip()
        if v:
            selected_teacher_ids = [v]
    if not selected_subjects and request.GET.get('subject'):
        v = str(request.GET.get('subject', '')).strip()
        if v:
            selected_subjects = [v]

    selected_level = selected_levels[0] if len(selected_levels) == 1 else (selected_levels[0] if selected_levels else '')
    selected_subject = selected_subjects[0] if len(selected_subjects) == 1 else (selected_subjects[0] if selected_subjects else '')
    selected_teacher_id = selected_teacher_ids[0] if len(selected_teacher_ids) == 1 else (selected_teacher_ids[0] if selected_teacher_ids else '')

    # وضع الإسناد الديناميكي للأستاذ: مفعّل افتراضياً، ويمكن إلغاؤه من الواجهة
    dynamic_assignment = request.GET.get('dynamic_assignment', 'true') == 'true'

    # احتساب الأصفار: الافتراضي عدم الاحتساب؛ التفعيل عبر تحديد الـ checkbox أو ?include_zeros=true
    include_zeros = request.GET.get('include_zeros') == 'true'

    from .school_year_utils import get_current_school_year
    current_school_year = get_current_school_year()
    grades_qs = Grade.objects.filter(academic_year=current_school_year)
    grades_qs_for_teacher_compare = Grade.objects.filter(academic_year=current_school_year)
    if selected_terms:
        grades_qs = grades_qs.filter(term__in=selected_terms)

    # Subject Filtering
    if selected_subjects:
        import django.db.models as models
        q_subj = models.Q()
        for s in selected_subjects:
            q_subj |= models.Q(subject__icontains=s)
        grades_qs = grades_qs.filter(q_subj)

    # تطبيع رمز القسم إلى صيغة 1م1 ليتطابق مع student.class_code أو academic_year+class_name
    def _normalize_class_code(raw):
        if not raw:
            return None
        v = re.sub(r'\s+', ' ', str(raw).strip()).strip()
        if not v:
            return None
        m = re.match(r'^(\d+)م(\d+)$', v)
        if m:
            return v.replace(' ', '')
        m = re.match(r'^(\d+)\s*م\s*(\d+)$', v)
        if m:
            return m.group(1) + 'م' + m.group(2)
        arb_to_digit = {'أولى': '1', 'ثانية': '2', 'ثالثة': '3', 'رابعة': '4'}
        for arb, digit in arb_to_digit.items():
            if arb in v or digit in v:
                num_match = re.search(r'(\d+)', v)
                section = num_match.group(1) if num_match else '1'
                return digit + 'م' + section
        return v

    # Teacher Assignment Filtering - Clean Refactor using class_code (يُفعّل فقط عند تفعيل الإسناد الديناميكي)
    teacher_classes = []
    teacher_subjects = []
    if dynamic_assignment and selected_teacher_ids:
        from .models import Employee, TeacherAssignment
        for tid in selected_teacher_ids:
            try:
                teacher = Employee.objects.get(id=tid)
                if teacher.analytics_assignments and isinstance(teacher.analytics_assignments, list) and len(teacher.analytics_assignments) > 0:
                    for assign in teacher.analytics_assignments:
                        subj = assign.get('subject', '').strip()
                        if selected_subjects and not any(s.lower() in subj.lower() for s in selected_subjects):
                            continue
                        if subj and subj != '/' and subj not in teacher_subjects:
                            teacher_subjects.append(subj)
                        classes_list = assign.get('classes') or []
                        if isinstance(classes_list, str):
                            classes_list = [x.strip() for x in str(classes_list).replace('،', ',').split(',') if x.strip()]
                        if classes_list:
                            for c in classes_list:
                                v = str(c).strip()
                                if v:
                                    teacher_classes.append(v)
                                    norm = _normalize_class_code(c)
                                    if norm and norm != v:
                                        teacher_classes.append(norm)
                        else:
                            # إذا كان إسناد التحليل موجوداً لكن بدون أقسام (مثلاً تم استيراد المواد فقط)،
                            # نرجع تلقائياً إلى أقسام الموارد البشرية لنفس المادة حتى تعمل فلترة الأفواج
                            if subj:
                                hr_qs = TeacherAssignment.objects.filter(teacher=teacher, subject__icontains=subj)
                                for ha in hr_qs:
                                    if ha.classes:
                                        for c in ha.classes:
                                            v = str(c).strip()
                                            if v:
                                                teacher_classes.append(v)
                                                norm = _normalize_class_code(c)
                                                if norm and norm != v:
                                                    teacher_classes.append(norm)
                else:
                    assignments = TeacherAssignment.objects.filter(teacher=teacher)
                    if selected_subjects:
                        import django.db.models as models
                        qs = models.Q()
                        for s in selected_subjects:
                            qs |= models.Q(subject__icontains=s)
                        assignments = assignments.filter(qs)
                    for assign in assignments:
                        if assign.classes:
                            for c in assign.classes:
                                v = str(c).strip()
                                if v:
                                    teacher_classes.append(v)
                                    norm = _normalize_class_code(c)
                                    if norm and norm != v:
                                        teacher_classes.append(norm)
                        if assign.subject and assign.subject != '/' and assign.subject not in teacher_subjects:
                            teacher_subjects.append(assign.subject)
            except Employee.DoesNotExist:
                pass

        teacher_classes = list(set(teacher_classes))

        # بعد توحيد المواد مع مواد النتائج: عند فلترة أستاذ فقط، فعّل تلقائياً كل مواده التدريسية في الفلتر
        if teacher_subjects and not selected_subjects:
            selected_subjects = list(teacher_subjects)

        # عند اختيار مستوى مع الأستاذ: نستخدم تقاطع أقسام الأستاذ مع المستوى فقط (مع تطبيع الرموز)
        # إذا كان التقاطع فارغاً (مثلاً المستوى "أولى" والأستاذ مسند لـ 4م1،4م2) نلغي مستوى الفلتر ونبقي أقسام الأستاذ
        if selected_levels and teacher_classes:
            level_classes = []
            for sl in selected_levels:
                level_classes.extend(class_map.get(sl) or class_map.get(sl + ' متوسط') or [])
            level_classes = list(set(level_classes))
            if level_classes:
                level_set = set(str(c).strip() for c in level_classes)
                for tc in level_classes:
                    n = _normalize_class_code(tc)
                    if n:
                        level_set.add(n)
                effective = [c for c in teacher_classes if (c in level_set or _normalize_class_code(c) in level_set)]
                if effective:
                    teacher_classes = effective
                else:
                    # تقاطع فارغ: نلغي فلتر المستوى حتى تظهر أقسام الأستاذ فقط
                    selected_levels = []
                    selected_level = ''

        # Normalize teacher_classes: توحيد الصيغ (1م1، 1p4، أولى 1) لاستخدامها في الفلتر
        if teacher_classes:
            resolved_codes = set()
            for tc in teacher_classes:
                v = str(tc).strip()
                if not v:
                    continue
                resolved_codes.add(v)
                n = re.sub(r'([0-9])[pP]([0-9])', r'\1م\2', v)
                if n != v:
                    resolved_codes.add(n)
                norm = _normalize_class_code(v)
                if norm:
                    resolved_codes.add(norm)
            teacher_classes = list(resolved_codes)

            import django.db.models as models
            q_teacher = models.Q(student__class_code__in=teacher_classes)
            arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
            for tc in teacher_classes:
                v = str(tc).strip()
                m = re.match(r'^(\d+)م(\d+)$', v)
                if m:
                    lvl_digit, section_num = m.group(1), m.group(2)
                    arb_word = arb_map.get(lvl_digit, lvl_digit)
                    q_teacher |= (
                        (models.Q(student__academic_year__icontains=arb_word) |
                         models.Q(student__academic_year__icontains=lvl_digit))
                        & models.Q(student__class_name__icontains=section_num)
                    )
            grades_qs = grades_qs.filter(q_teacher)

    # Move auto-selection logic here: عند فلترة أستاذ نفعّل مستواه وأفواجه فقط عند تفعيل الإسناد الديناميكي
    if dynamic_assignment and selected_teacher_id and teacher_classes:
        import re
        # استخراج المستويات من class_map (مفتاح المستوى الذي يضم كل فوج) لضمان ظهور كل المستويات المسندة
        temp_levels = []
        normalized_teacher_classes = set()
        for tc in teacher_classes:
            v = str(tc).strip()
            normalized_teacher_classes.add(v)
            n = re.sub(r'([0-9])[pP]([0-9])', r'\1م\2', v)
            normalized_teacher_classes.add(n)
        for lvl, clist in class_map.items():
            for c in clist:
                c_norm = re.sub(r'([0-9])[pP]([0-9])', r'\1م\2', str(c).strip())
                if c in normalized_teacher_classes or c_norm in normalized_teacher_classes or any(tc in str(c) or str(c) in tc for tc in normalized_teacher_classes):
                    if lvl not in temp_levels:
                        temp_levels.append(lvl)
                    break
        if not temp_levels:
            for tc in teacher_classes:
                m = re.match(r'(\d+)م', tc)
                if m:
                    lvl_digit = m.group(1)
                    arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                    arb_lvl = arb_map.get(lvl_digit, lvl_digit) + ' متوسط'
                    if arb_lvl not in temp_levels and arb_lvl in class_map:
                        temp_levels.append(arb_lvl)

        if not selected_levels and temp_levels:
            selected_levels = list(temp_levels)
            selected_level = selected_levels[0] if selected_levels else ''

        # أفواج الأستاذ ضمن المستويات المختارة
        level_classes = []
        for sl in (selected_levels or []):
            level_classes.extend(class_map.get(sl) or class_map.get(sl + ' متوسط') or [])
        level_classes = list(set(level_classes))
        level_set = set(level_classes)
        valid_classes_for_lvl = [c for c in teacher_classes if c in level_set] if level_set else list(teacher_classes)
        if not selected_classes and valid_classes_for_lvl:
            selected_classes = list(valid_classes_for_lvl)

        if selected_levels and not selected_level:
            selected_level = selected_levels[0]

    # Now apply the global filters strictly using class_code/academic_year to avoid bugs
    if selected_levels and not (selected_teacher_ids and teacher_classes):
        import django.db.models as models
        q_lvl = models.Q()
        for sl in selected_levels:
            q_lvl |= (models.Q(student__academic_year=sl) |
                      models.Q(student__academic_year__icontains=(sl or '').replace(' متوسط', '').strip()))
        grades_qs = grades_qs.filter(q_lvl)
    if selected_classes and selected_levels:
        # لا نطبق فلترة الأقسام إلا عند اختيار مستوى (الأقسام مرتبطة بالمستوى)
        import django.db.models as models
        code_classes = [c for c in selected_classes if re.match(r'^\d+م\d+$', str(c).strip())]
        other_classes = [c for c in selected_classes if c not in code_classes]
        q_class = models.Q()
        if code_classes:
            # أولاً: محاولة المطابقة مباشرة مع class_code إن كانت معبأة
            q_class |= models.Q(student__class_code__in=code_classes)
            # ثانياً: fallback عند غياب class_code (معظم الحالات الحالية) بالاعتماد على (المستوى، رقم الفوج)
            arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
            for cc in code_classes:
                m = re.match(r'^(\d+)م(\d+)$', str(cc).strip())
                if not m:
                    continue
                lvl_digit, section_num = m.group(1), m.group(2)
                arb_lvl = arb_map.get(lvl_digit, lvl_digit)
                # نبحث عن التلاميذ الذين مستوى دراستهم يطابق الرقم أو الاسم العربي، ورقم القسم يحتوي رقم الفوج
                q_class |= (
                    (models.Q(student__academic_year__icontains=arb_lvl) |
                     models.Q(student__academic_year__icontains=lvl_digit))
                    & models.Q(student__class_name__icontains=section_num)
                )
        for c in other_classes:
            from .analytics_utils import unformat_class_name
            raw_class = unformat_class_name(c)
            if raw_class and raw_class.isdigit():
                q_class |= (models.Q(student__class_name=c) | models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__icontains=raw_class))
            else:
                q_class |= models.Q(student__class_name=c)
        grades_qs = grades_qs.filter(q_class)

    effective_subject = selected_subject
    if selected_teacher_id and not effective_subject and teacher_subjects:
        # If filtering by teacher but no specific subject is chosen, and they only teach one subject, use it
        if len(teacher_subjects) == 1:
            effective_subject = teacher_subjects[0]

    # ترتيب التلاميذ: حسب الفلترة إن وُجدت، وإلا حسب المعدل الفصلي (كل المواد)
    has_filter = bool(selected_terms or selected_levels or selected_classes or selected_subjects or selected_teacher_ids)
    grades_qs_for_ranking = None
    if not has_filter:
        # عدم اختيار فلتر: الترتيب على أساس المعدل الفصلي (كل المواد، بدون فلتر مادة)
        grades_qs_for_ranking = Grade.objects.filter(academic_year=current_school_year)

    settings_obj = SchoolSettings.objects.first()
    exempt_subjects = list(settings_obj.analytics_exempt_subjects) if settings_obj and getattr(settings_obj, 'analytics_exempt_subjects', None) else []
    # قواعد إعفاء مادة حسب (تلميذ/فوج/مستوى/مؤسسة)
    exemption_rules = []
    try:
        from .models import SubjectExemptionRule
        for r in SubjectExemptionRule.objects.all().order_by('-created_at')[:500]:
            exemption_rules.append({
                'id': r.id,
                'subject': r.subject,
                'scope_type': r.scope_type,
                'student_id': r.student_id,
                'academic_year': r.academic_year,
                'class_code': r.class_code,
                'term': r.term,
            })
    except Exception:
        exemption_rules = []

    # إضافة المواد المعفاة بالمؤسسة (بدون فصل) إلى exempt_subjects لاستبعادها من كل الحسابات والترتيب
    for r in exemption_rules:
        if r.get('scope_type') == 'school' and (r.get('subject') or '').strip() and not (r.get('term') or '').strip():
            s = str(r.get('subject')).strip()
            if s and s not in exempt_subjects:
                exempt_subjects.append(s)

    # مجالات الإجازات (تُستخدم لاحقاً في تطبيق الملاحظة على ترتيب التلاميذ وفي القالب)
    award_defaults = {'امتياز': 16, 'تهنئة': 14, 'تشجيع': 12, 'لوحة شرف': 10}
    award_thresholds_raw = getattr(settings_obj, 'award_thresholds', None) if settings_obj else None
    if isinstance(award_thresholds_raw, dict):
        award_thresholds = {k: award_thresholds_raw.get(k) if award_thresholds_raw.get(k) is not None else award_defaults.get(k) for k in ['امتياز', 'تهنئة', 'تشجيع', 'لوحة شرف']}
    else:
        award_thresholds = award_defaults.copy()

    def _award_val(d, key, default):
        v = d.get(key)
        if v is not None and v != '':
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
        return default

    local_stats = analyze_grades_locally(
        grades_qs,
        subject_filter=effective_subject,
        include_zeros=include_zeros,
        grades_qs_for_ranking=grades_qs_for_ranking,
        exempt_subjects=exempt_subjects,
        exemption_rules=exemption_rules
    )

    # Re-calculate exact total students from Student model based on filters to account for students without grades yet
    if local_stats is not None:
        from .models import Student
        import django.db.models as models
        import re
        student_qs = Student.objects.all()

        if dynamic_assignment and selected_teacher_id and teacher_classes:
            q_teacher_st = models.Q(class_code__in=teacher_classes)
            arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
            for tc in teacher_classes:
                m = re.match(r'^(\d+)م(\d+)$', str(tc).strip())
                if m:
                    lvl_digit, section_num = m.group(1), m.group(2)
                    arb_word = arb_map.get(lvl_digit, lvl_digit)
                    q_teacher_st |= (
                        (models.Q(academic_year__icontains=arb_word) |
                         models.Q(academic_year__icontains=lvl_digit))
                        & models.Q(class_name__icontains=section_num)
                    )
            student_qs = student_qs.filter(q_teacher_st)

        if selected_levels and not (selected_teacher_ids and teacher_classes):
            q_lvl = models.Q()
            for sl in selected_levels:
                q_lvl |= (models.Q(academic_year=sl) |
                          models.Q(academic_year__icontains=(sl or '').replace(' متوسط', '').strip()))
            student_qs = student_qs.filter(q_lvl)

        if selected_classes and selected_levels:
            import re
            code_classes = [c for c in selected_classes if re.match(r'^\d+م\d+$', str(c).strip())]
            other_classes = [c for c in selected_classes if c not in code_classes]
            q_class = models.Q()
            if code_classes:
                # مطابقة مباشرة على class_code إن وُجد
                q_class |= models.Q(class_code__in=code_classes)
                # Fallback باستخدام (المستوى، رقم الفوج) عندما يكون class_code فارغاً
                arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                for cc in code_classes:
                    m = re.match(r'^(\d+)م(\d+)$', str(cc).strip())
                    if not m:
                        continue
                    lvl_digit, section_num = m.group(1), m.group(2)
                    arb_lvl = arb_map.get(lvl_digit, lvl_digit)
                    q_class |= (
                        (models.Q(academic_year__icontains=arb_lvl) |
                         models.Q(academic_year__icontains=lvl_digit))
                        & models.Q(class_name__icontains=section_num)
                    )
            for c in other_classes:
                from .analytics_utils import unformat_class_name
                raw_class = unformat_class_name(c)
                if raw_class and raw_class.isdigit():
                    q_class |= (models.Q(class_name=c) | models.Q(class_name=raw_class) |
                        models.Q(class_name__endswith=f" {raw_class}") |
                        models.Q(class_name__icontains=raw_class))
                else:
                    q_class |= models.Q(class_name=c)
            student_qs = student_qs.filter(q_class)

        local_stats['total_students'] = student_qs.count()
        local_stats['total_males'] = student_qs.filter(gender='ذكر').count()
        local_stats['total_females'] = student_qs.filter(gender='أنثى').count()
        local_stats['total_repeaters'] = student_qs.filter(is_repeater=True).count()

    # تطبيق مجالات الإجازات على ترتيب التلاميذ (الملاحظة حسب المعدل الفصلي)
    if local_stats and award_thresholds and isinstance(local_stats.get('ranking_list'), list):
        t_emtyaz = _award_val(award_thresholds, 'امتياز', 16)
        t_tahnia = _award_val(award_thresholds, 'تهنئة', 14)
        t_tashjeeb = _award_val(award_thresholds, 'تشجيع', 12)
        t_lawha = _award_val(award_thresholds, 'لوحة شرف', 10)
        for r in local_stats['ranking_list']:
            if r.get('is_absent'):
                r['remark'] = ''
                continue
            try:
                score = float(r.get('score') or 0)
            except (TypeError, ValueError):
                r['remark'] = ''
                continue
            if score >= t_emtyaz:
                r['remark'] = 'امتياز'
            elif score >= t_tahnia:
                r['remark'] = 'تهنئة'
            elif score >= t_tashjeeb:
                r['remark'] = 'تشجيع'
            elif score >= t_lawha:
                r['remark'] = 'لوحة شرف'
            else:
                r['remark'] = ''
        import json as _json
        local_stats['ranking_list_json'] = _json.dumps(local_stats['ranking_list'])

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

    import json

    # قائمة المواد في واجهة تحليل النتائج: من ملف الإكسل (Grade) فقط، كما هي بدون زيادة أو حذف
    teacher_subjects = locals().get('teacher_subjects', [])
    teacher_classes = locals().get('teacher_classes', [])

    from .import_utils import get_deduplicated_subjects_from_grades
    subjects_list = get_deduplicated_subjects_from_grades()

    # Filter class_map to only show teacher classes if selected
    teacher_info = None
    if dynamic_assignment and selected_teacher_id and teacher_classes:
        # Normalize teacher_classes to class_code format (1م1) for matching
        from .models_mapping import ClassAlias

        def _normalize_class_code(val):
            if not val or not str(val).strip():
                return set()
            v = str(val).strip()
            # 1p4 -> 1م4, 2P1 -> 2م1 (p/P = متوسط)
            n = re.sub(r'([0-9])[pP]([0-9])', r'\1م\2', v)
            if n != v:
                return {v, n}
            return {v}

        teacher_classes_normalized = set()
        for tc in teacher_classes:
            teacher_classes_normalized.add(str(tc).strip())
            for n in _normalize_class_code(tc):
                teacher_classes_normalized.add(n)
            # Resolve via ClassAlias if exists
            try:
                alias = ClassAlias.objects.get(alias=str(tc).strip())
                canon = f"{alias.canonical_level} {alias.canonical_class}".strip()
                m = re.search(r'(\d+)[مmM]\s*(\d+)', canon) or re.search(r'(\d+)\s*متوسط\s*(\d+)', canon)
                if m:
                    teacher_classes_normalized.add(f"{m.group(1)}م{m.group(2)}")
            except (ClassAlias.DoesNotExist, Exception):
                pass
        # Also add 1p4 -> 1م4 variants
        for tc in list(teacher_classes_normalized):
            for n in _normalize_class_code(tc):
                teacher_classes_normalized.add(n)

        filtered_class_map = {}
        for lvl, clist in class_map.items():
            valid_cls = []
            for c in clist:
                from .analytics_utils import unformat_class_name
                raw_c = unformat_class_name(c)
                short_c = c
                m = re.search(r'(\d+)\s*متوسط\s*(\d+)', str(c))
                if m:
                    short_c = f"{m.group(1)}م{m.group(2)}"
                if c in teacher_classes_normalized or raw_c in teacher_classes_normalized or short_c in teacher_classes_normalized:
                    valid_cls.append(c)
                elif any(tc in str(c) or str(c) in str(tc) for tc in teacher_classes_normalized):
                    valid_cls.append(c)

            if valid_cls:
                filtered_class_map[lvl] = valid_cls

        class_map = filtered_class_map
        levels = list(class_map.keys())

        # Re-sort levels to keep them in a logical order (1, 2, 3, 4)
        def level_sort_key(lvl):
            import re
            m = re.search(r'\d+', str(lvl))
            if m:
                return int(m.group(0))
            return 999

        levels = sorted(levels, key=level_sort_key)

        # Ensure the selected_levels and selected_classes context matches the ones we auto-selected earlier
        if selected_levels and levels and selected_levels[0] not in levels:
            selected_levels = [levels[0]]
            selected_level = selected_levels[0]

        try:
            from .models import Employee
            teacher_obj = Employee.objects.get(id=selected_teacher_id)
            teacher_info = {
                'name': f"{teacher_obj.last_name} {teacher_obj.first_name}",
                'subjects': "، ".join(teacher_subjects),
                'classes': "، ".join(teacher_classes)
            }
        except Exception:
            pass

    # Get Teachers List for Dropdown (عند الفلترة بالمادة: فقط أساتذة تلك المادة)
    from .models import Employee, TeacherAssignment
    teachers = list(Employee.objects.filter(rank='teacher').order_by('last_name'))

    # Build teacher->subjects/classes and subject->teachers for dynamic filtering
    teacher_assignments_map = {}
    subject_teachers_map = {}
    for t in teachers:
        tid = str(t.id)
        subjs, clss = [], []
        if t.analytics_assignments and isinstance(t.analytics_assignments, list):
            for a in t.analytics_assignments:
                s = (a.get('subject') or '').strip()
                if s and s != '/':
                    subjs.append(s)
                    lst = subject_teachers_map.setdefault(s, [])
                    if tid not in lst:
                        lst.append(tid)
                clss.extend(a.get('classes') or [])
        for ta in TeacherAssignment.objects.filter(teacher=t):
            s = (ta.subject or '').strip()
            if s and s != '/':
                if s not in subjs:
                    subjs.append(s)
                    lst = subject_teachers_map.setdefault(s, [])
                    if tid not in lst:
                        lst.append(tid)
                clss.extend(ta.classes or [])
        teacher_assignments_map[tid] = {'subjects': list(set(subjs)), 'classes': list(set(clss))}

    # نسخة كاملة من جميع الأساتذة (لأغراض ربط الأساتذة بمواد النتائج بعد الاستيراد)
    from .models import Employee
    all_teachers_for_tls = list(Employee.objects.filter(rank='teacher').only('id', 'last_name', 'first_name', 'subject'))

    # عند الفلترة بالمادة: إظهار أساتذة تلك المادة فقط في القائمة (قائمة الفلترة الرئيسية فقط)
    if selected_subjects:
        teacher_ids_for_subjects = set()
        for s in selected_subjects:
            teacher_ids_for_subjects.update(subject_teachers_map.get(s, []))
        if teacher_ids_for_subjects:
            teachers = [t for t in teachers if str(t.id) in teacher_ids_for_subjects]

    # أسماء الأساتذة المختارين (للعرض في التسمية بدل "x أستاذ")
    selected_teacher_names_list = []
    if selected_teacher_ids:
        id_to_name = {str(t.id): f"{t.last_name} {t.first_name}" for t in Employee.objects.filter(id__in=selected_teacher_ids).only('id', 'last_name', 'first_name')}
        selected_teacher_names_list = [id_to_name.get(tid, '') for tid in selected_teacher_ids if id_to_name.get(tid)]
        selected_teacher_names_list = [n for n in selected_teacher_names_list if n]

    # Analysis scope description (what's being calculated)
    analysis_scope_parts = []
    if selected_subject:
        analysis_scope_parts.append(f"المادة: {selected_subject}")
    if selected_teacher_id and teacher_info:
        analysis_scope_parts.append(f"الأستاذ: {teacher_info['name']}")
        if teacher_subjects:
            analysis_scope_parts.append(f"مواده: {', '.join(teacher_subjects)}")
    if selected_levels:
        analysis_scope_parts.append(f"المستوى: {'، '.join(selected_levels)}")
    if selected_classes:
        analysis_scope_parts.append(f"الأقسام: {', '.join(selected_classes)}")
    analysis_scope = " | ".join(analysis_scope_parts) if analysis_scope_parts else "كل البيانات"

    exempt_subjects_list = list(settings_obj.analytics_exempt_subjects) if settings_obj and getattr(settings_obj, 'analytics_exempt_subjects', None) else []
    award_emtyaz = _award_val(award_thresholds, 'امتياز', 16)
    award_tahnia = _award_val(award_thresholds, 'تهنئة', 14)
    award_tashjeeb = _award_val(award_thresholds, 'تشجيع', 12)
    award_lawha = _award_val(award_thresholds, 'لوحة شرف', 10)
    context = {
        'page_title': 'تحليل النتائج',
        'local_stats': local_stats,
        'award_thresholds': award_thresholds,
        'award_emtyaz': award_emtyaz,
        'award_tahnia': award_tahnia,
        'award_tashjeeb': award_tashjeeb,
        'award_lawha': award_lawha,
        'levels': levels,
        'class_map_json': json.dumps(class_map),
        'token_cost': token_cost,
        'teachers': teachers,
        'all_teachers_for_tls': all_teachers_for_tls,
        'teacher_info': teacher_info,
        'teacher_assignments_map_json': json.dumps(teacher_assignments_map),
        'subject_teachers_map_json': json.dumps(subject_teachers_map),
        'subjects_list': subjects_list,
        'analytics_exempt_subjects': exempt_subjects_list,
        'exemption_rules': exemption_rules,
        'selected_teacher_id': selected_teacher_id,
        'selected_subject': selected_subject,
        'selected_level': selected_level,
        'selected_teacher_ids_list': [str(x) for x in selected_teacher_ids],
        'selected_teacher_names_list': selected_teacher_names_list,
        'selected_subjects_list': selected_subjects,
        'selected_levels_list': selected_levels,
        'selected_terms_list': selected_terms,
        'selected_classes': selected_classes,
        'selected_classes_json': json.dumps(selected_classes),
        'analysis_scope': analysis_scope,
        'teacher_classes': teacher_classes,
        'dynamic_assignment': dynamic_assignment,
    }
    return render(request, 'students/analytics.html', context)

def advanced_analytics_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_advanced_analytics')):
        return redirect('dashboard')

    from .models import Grade
    import pandas as pd

    # Global Filters
    selected_level = request.GET.get('level', '')
    selected_class = request.GET.get('class_name', '')
    selected_teacher_id = request.GET.get('teacher_id', '')
    selected_subject = request.GET.get('subject', '')
    teacher_compare_ids = request.GET.getlist('teacher_compare') or request.GET.getlist('teacher_compare_ids')

    from .school_year_utils import get_current_school_year
    current_school_year = get_current_school_year()
    grades_qs = Grade.objects.filter(academic_year=current_school_year)

    # Apply Filters to the QuerySet
    # Compute teacher subjects BEFORE filtering the assignments by selected_subject
    teacher_subjects = []
    teacher_classes = []
    teacher_info = None

    if selected_teacher_id:
        from .models import Employee, TeacherAssignment
        try:
            teacher = Employee.objects.get(id=selected_teacher_id)
            if teacher.analytics_assignments and isinstance(teacher.analytics_assignments, list) and len(teacher.analytics_assignments) > 0:
                for assign in teacher.analytics_assignments:
                    subj = assign.get('subject', '').strip()
                    if subj and subj != '/' and subj not in teacher_subjects:
                        teacher_subjects.append(subj)
            else:
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
        grades_qs_for_teacher_compare = grades_qs_for_teacher_compare.filter(models.Q(subject__icontains=selected_subject))

    if selected_teacher_id:
        from .models import Employee, TeacherAssignment
        try:
            teacher = Employee.objects.get(id=selected_teacher_id)
            teacher_classes = []

            if teacher.analytics_assignments and isinstance(teacher.analytics_assignments, list) and len(teacher.analytics_assignments) > 0:
                 for assign in teacher.analytics_assignments:
                      subj = assign.get('subject', '').strip()
                      if selected_subject and selected_subject.lower() not in subj.lower():
                           continue
                      if assign.get('classes'):
                           teacher_classes.extend(assign.get('classes'))
            else:
                assignments = TeacherAssignment.objects.filter(teacher=teacher)

                if selected_subject:
                    assignments = assignments.filter(subject__icontains=selected_subject)

                for assign in assignments:
                    if assign.classes:
                        teacher_classes.extend(assign.classes)

            teacher_classes = list(set(teacher_classes))

            if teacher_classes:
                # فلترة أفواج الأستاذ: class_code إن وُجد، وإلا fallback على (المستوى + رقم الفوج)
                import django.db.models as models
                import re
                q_teacher = models.Q(student__class_code__in=teacher_classes)
                arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                for cc in teacher_classes:
                    m = re.match(r'^(\d+)م(\d+)$', str(cc).strip())
                    if not m:
                        continue
                    lvl_digit, section_num = m.group(1), m.group(2)
                    arb_lvl = arb_map.get(lvl_digit, lvl_digit)
                    q_teacher |= (
                        (models.Q(student__academic_year__icontains=arb_lvl) |
                         models.Q(student__academic_year__icontains=lvl_digit))
                        & models.Q(student__class_name__icontains=section_num)
                    )
                    # دعم قوي عندما يكون class_name مثل: "رابعة 1"
                    q_teacher |= (
                        models.Q(student__class_name__icontains=arb_lvl)
                        & models.Q(student__class_name__icontains=section_num)
                    )
                grades_qs = grades_qs.filter(q_teacher)

            if teacher_subjects and not selected_subject:
                import django.db.models as models
                q_subjs = models.Q()
                for subj in teacher_subjects:
                    q_subjs |= models.Q(subject__icontains=subj)
                grades_qs = grades_qs.filter(q_subjs)

        except Employee.DoesNotExist:
            pass

    # Teacher info for UI badge
    if selected_teacher_id:
        try:
            from .models import Employee
            t = Employee.objects.get(id=selected_teacher_id)
            teacher_info = {
                'name': f"{t.last_name} {t.first_name}",
                'subjects': "، ".join(teacher_subjects) if teacher_subjects else (t.subject or '/'),
                'classes': "، ".join(teacher_classes) if teacher_classes else '—',
            }
        except Exception:
            teacher_info = None

    # Apply global level/class filters ONLY if no teacher is selected (or if we want them to narrow down teacher classes)
    if selected_level:
        import django.db.models as models
        grades_qs = grades_qs.filter(
            models.Q(student__academic_year=selected_level) |
            models.Q(student__academic_year__icontains=selected_level.replace(' متوسط', '').strip())
        )
        grades_qs_for_teacher_compare = grades_qs_for_teacher_compare.filter(
            models.Q(student__academic_year=selected_level) |
            models.Q(student__academic_year__icontains=selected_level.replace(' متوسط', '').strip())
        )
    if selected_class:
        import re
        if re.match(r'^\d+م\d+$', selected_class):
            grades_qs = grades_qs.filter(student__class_code=selected_class)
            grades_qs_for_teacher_compare = grades_qs_for_teacher_compare.filter(student__class_code=selected_class)
        else:
            from .analytics_utils import unformat_class_name
            import django.db.models as models
            raw_class = unformat_class_name(selected_class)
            if raw_class and raw_class.isdigit():
                grades_qs = grades_qs.filter(
                    models.Q(student__class_name=selected_class) |
                    models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__icontains=raw_class)
                )
                grades_qs_for_teacher_compare = grades_qs_for_teacher_compare.filter(
                    models.Q(student__class_name=selected_class) |
                    models.Q(student__class_name=raw_class) |
                    models.Q(student__class_name__endswith=f" {raw_class}") |
                    models.Q(student__class_name__icontains=raw_class)
                )
            else:
                grades_qs = grades_qs.filter(student__class_name=selected_class)
                grades_qs_for_teacher_compare = grades_qs_for_teacher_compare.filter(student__class_name=selected_class)

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

    # Teacher comparison stats (multi-teacher)
    teacher_compare_stats = {}
    try:
        from .models import Employee, TeacherAssignment
        import django.db.models as models
        import re
        compare_ids = [str(x).strip() for x in (teacher_compare_ids or []) if str(x).strip()]
        if compare_ids:
            base_qs = grades_qs_for_teacher_compare
            for tid in compare_ids:
                try:
                    emp = Employee.objects.get(id=int(tid))
                except Exception:
                    continue
                t_classes = []
                t_subjects = []
                if emp.analytics_assignments and isinstance(emp.analytics_assignments, list) and len(emp.analytics_assignments) > 0:
                    for a in emp.analytics_assignments:
                        subj = (a.get('subject') or '').strip()
                        if subj and subj != '/' and subj not in t_subjects:
                            t_subjects.append(subj)
                        for c in a.get('classes', []) or []:
                            v = str(c).strip()
                            if v:
                                t_classes.append(v)
                else:
                    for a in TeacherAssignment.objects.filter(teacher=emp):
                        if a.subject and a.subject != '/' and a.subject not in t_subjects:
                            t_subjects.append(a.subject)
                        for c in a.classes or []:
                            v = str(c).strip()
                            if v:
                                t_classes.append(v)
                t_classes = list(set(t_classes))

                qs_t = base_qs
                if t_classes:
                    # class_code إن وُجد، وإلا fallback على (المستوى + رقم الفوج) من class_name
                    q_teacher = models.Q(student__class_code__in=t_classes)
                    arb_map = {'1': 'أولى', '2': 'ثانية', '3': 'ثالثة', '4': 'رابعة'}
                    for cc in t_classes:
                        m = re.match(r'^(\d+)م(\d+)$', str(cc).strip())
                        if not m:
                            continue
                        lvl_digit, section_num = m.group(1), m.group(2)
                        arb_lvl = arb_map.get(lvl_digit, lvl_digit)
                        q_teacher |= (
                            (models.Q(student__academic_year__icontains=arb_lvl) |
                             models.Q(student__academic_year__icontains=lvl_digit))
                            & models.Q(student__class_name__icontains=section_num)
                        )
                        # دعم قوي عندما يكون class_name مثل: "رابعة 1"
                        q_teacher |= (
                            models.Q(student__class_name__icontains=arb_lvl)
                            & models.Q(student__class_name__icontains=section_num)
                        )
                    qs_t = qs_t.filter(q_teacher)
                if not selected_subject and t_subjects:
                    q_subj = models.Q()
                    for s in t_subjects:
                        q_subj |= models.Q(subject__icontains=s)
                    qs_t = qs_t.filter(q_subj)

                df_t = pd.DataFrame(list(qs_t.values('student__id', 'score')))
                if not df_t.empty:
                    df_t = df_t[df_t['score'] > 0]
                if df_t.empty:
                    # Keep teacher entry so UI shows "0" instead of disappearing
                    teacher_compare_stats[str(emp.id)] = {'name': f"{emp.last_name} {emp.first_name}", 'count': 0, 'avg': 0.0, 'success_pct': 0.0}
                    continue
                means = df_t.groupby('student__id')['score'].mean()
                n = int(means.shape[0])
                avg = float(round(means.mean(), 2)) if n else 0.0
                succ = int((means >= 10).sum())
                succ_pct = float(round((succ / n) * 100, 2)) if n else 0.0
                teacher_compare_stats[str(emp.id)] = {'name': f"{emp.last_name} {emp.first_name}", 'count': n, 'avg': avg, 'success_pct': succ_pct}
    except Exception:
        teacher_compare_stats = {}

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

    # Get Dynamic Subjects List (مُطبّعة وبدون تكرار)
    from .import_utils import get_deduplicated_subjects_from_grades
    subjects_list = get_deduplicated_subjects_from_grades()

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
        'teacher_info': teacher_info,
        'selected_level': selected_level,
        'selected_class': selected_class,
        'selected_teacher_id': selected_teacher_id,
        'selected_subject': selected_subject,
        'teacher_compare_ids': teacher_compare_ids,
        'teacher_compare_stats_json': json.dumps(teacher_compare_stats, ensure_ascii=False),
    }
    return render(request, 'students/advanced_analytics.html', context)

def statistical_tests_view(request):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if not (request.user.is_superuser or request.user.username == 'director' or hasattr(request.user, 'profile') and request.user.profile.has_perm('access_advanced_analytics')):
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
    from .school_year_utils import get_current_school_year
    import pandas as pd
    import scipy.stats as stats

    current_school_year = get_current_school_year()
    grades_qs = Grade.objects.filter(academic_year=current_school_year)
    if level:
        import django.db.models as models
        # Also do a broad match for level just in case DB has 'أولى' but frontend passed 'أولى متوسط'
        grades_qs = grades_qs.filter(
            models.Q(student__academic_year=level) |
            models.Q(student__academic_year__icontains=level.replace(' متوسط', '').strip())
        )

    if not grades_qs.exists():
        return JsonResponse({'error': 'لا توجد بيانات كافية'})

    if grouping == 'teacher':
        # To compare teachers accurately, we must not average by student globally.
        # We must link specific grades (by subject and class) to the teacher who teaches that subject to that class.
        df = pd.DataFrame(list(grades_qs.values('student__id', 'student__academic_year', 'student__class_name', 'subject', 'score')))
        df = df[df['score'] > 0] # remove absences

        if df.empty:
            return JsonResponse({'error': 'لا توجد بيانات صحيحة بعد الفلترة'})

        from .models import TeacherAssignment
        import re

        # Build mapping: (shortcut_class, subject) -> teacher_name
        class_subj_to_teacher = {}
        from .models import Employee
        for teacher in Employee.objects.filter(rank='teacher'):
            t_name = f"{teacher.last_name} {teacher.first_name}"
            if teacher.analytics_assignments and isinstance(teacher.analytics_assignments, list) and len(teacher.analytics_assignments) > 0:
                for assign in teacher.analytics_assignments:
                    subj = assign.get('subject', '').strip()
                    for c in assign.get('classes', []):
                        class_subj_to_teacher[(c, subj)] = t_name
            else:
                for assign in TeacherAssignment.objects.filter(teacher=teacher):
                    subj = assign.subject
                    for c in assign.classes:
                        class_subj_to_teacher[(c, subj)] = t_name

        def get_teacher_for_grade(row):
            lvl = row['student__academic_year']
            cls = row['student__class_name']
            subj = row['subject']

            # Map to shortcut (e.g. 1م1)
            lvl_digit = "1"
            if "ثانية" in lvl or "2" in lvl: lvl_digit = "2"
            elif "ثالثة" in lvl or "3" in lvl: lvl_digit = "3"
            elif "رابعة" in lvl or "4" in lvl: lvl_digit = "4"

            cls_digit = "".join(re.findall(r'\d+', cls))
            if not cls_digit: cls_digit = "1"

            shortcut = f"{lvl_digit}م{cls_digit}"

            # Exact match
            if (shortcut, subj) in class_subj_to_teacher:
                return class_subj_to_teacher[(shortcut, subj)]

            # Fallback: fuzzy match on subject name (e.g. "رياضيات" vs "الرياضيات")
            for (c, s), t_name in class_subj_to_teacher.items():
                if c == shortcut and (s in subj or subj in s):
                    return t_name

            return "غير مسند"

        df['teacher_name'] = df.apply(get_teacher_for_grade, axis=1)
        # Filter out unassigned grades
        df = df[df['teacher_name'] != "غير مسند"]

        if df.empty:
            return JsonResponse({'error': 'لم يتم العثور على تقاطعات صحيحة بين العلامات والأساتذة'})

        # Now group by student and teacher so we don't have repeated measures for the same student/teacher pair (e.g. multiple terms)
        student_means = df.groupby(['student__id', 'teacher_name'])['score'].mean().reset_index()
        group_col = 'teacher_name'

    else:
        # Normal grouping (gender, class, etc.)
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
    arrays_named = []  # [(name, np.array)]

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
            arrays_named.append((str(name), scores))

    if len(arrays_for_test) < 2:
        return JsonResponse({'error': 'لا توجد مجموعات كافية للمقارنة (تتطلب مجموعتين على الأقل)'})

    statistic = 0.0
    p_value = 1.0
    test_name = ""
    effect = {}
    assumptions = {}
    post_hoc = None

    # Assumptions: Levene (homogeneity of variances)
    try:
        lev_stat, lev_p = stats.levene(*arrays_for_test, center='median')
        assumptions['levene'] = {'statistic': float(lev_stat), 'p_value': float(lev_p), 'ok': bool(lev_p >= 0.05)}
    except Exception:
        assumptions['levene'] = None

    # Assumptions: Shapiro-Wilk per group (small/medium only)
    try:
        shapiro = {}
        for gname, arr in arrays_named:
            if len(arr) < 3 or len(arr) > 5000:
                continue
            st, pv = stats.shapiro(arr)
            shapiro[gname] = {'statistic': float(st), 'p_value': float(pv), 'ok': bool(pv >= 0.05)}
        assumptions['shapiro'] = shapiro
    except Exception:
        assumptions['shapiro'] = {}

    if test_type == 't_test_ind':
        if len(arrays_for_test) > 2:
            return JsonResponse({'error': 'اختبار T-Test يتطلب مجموعتين فقط. استخدم ANOVA.'})
        test_name = "Independent T-Test"
        statistic, p_value = stats.ttest_ind(arrays_for_test[0], arrays_for_test[1], equal_var=False)
        # Effect size: Cohen's d (Hedges' g not needed here)
        try:
            import numpy as np
            a = np.array(arrays_for_test[0], dtype=float)
            b = np.array(arrays_for_test[1], dtype=float)
            na, nb = len(a), len(b)
            sa = float(a.std(ddof=1)) if na > 1 else 0.0
            sb = float(b.std(ddof=1)) if nb > 1 else 0.0
            sp = (((na - 1) * (sa ** 2) + (nb - 1) * (sb ** 2)) / max(na + nb - 2, 1)) ** 0.5
            d = float((a.mean() - b.mean()) / sp) if sp > 0 else 0.0
            effect['cohens_d'] = d
        except Exception:
            effect['cohens_d'] = None
    elif test_type == 'anova':
        test_name = "One-Way ANOVA"
        statistic, p_value = stats.f_oneway(*arrays_for_test)
        # Effect size: Eta squared
        try:
            import numpy as np
            all_vals = np.concatenate([np.array(x, dtype=float) for x in arrays_for_test])
            grand_mean = float(all_vals.mean()) if len(all_vals) else 0.0
            ss_between = 0.0
            ss_total = float(((all_vals - grand_mean) ** 2).sum()) if len(all_vals) else 0.0
            for _, arr in arrays_named:
                arr = np.array(arr, dtype=float)
                ss_between += len(arr) * ((float(arr.mean()) - grand_mean) ** 2)
            eta2 = float(ss_between / ss_total) if ss_total > 0 else 0.0
            effect['eta_squared'] = eta2
        except Exception:
            effect['eta_squared'] = None

        # Post-hoc: pairwise t-tests with Bonferroni correction
        try:
            import itertools
            pairs = []
            k = len(arrays_named)
            m = (k * (k - 1)) // 2 if k > 1 else 1
            for (n1, a), (n2, b) in itertools.combinations(arrays_named, 2):
                t, pv = stats.ttest_ind(a, b, equal_var=False)
                pv_adj = min(float(pv) * m, 1.0)
                pairs.append({
                    'group_a': n1,
                    'group_b': n2,
                    't_statistic': float(t),
                    'p_value': float(pv),
                    'p_value_bonferroni': pv_adj,
                    'significant_bonferroni': bool(pv_adj < 0.05),
                })
            post_hoc = {'method': 'pairwise_ttests_bonferroni', 'comparisons': pairs}
        except Exception:
            post_hoc = None
    else:
        return JsonResponse({'error': 'نوع الاختبار غير معروف'})

    return JsonResponse({
        'test_name': test_name,
        'statistic': float(statistic),
        'p_value': float(p_value),
        'is_significant': bool(p_value < 0.05),
        'groups': groups_data,
        'effect_size': effect,
        'assumptions': assumptions,
        'post_hoc': post_hoc,
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
            teacher_classes = []
            teacher_subjects = []

            if teacher.analytics_assignments and isinstance(teacher.analytics_assignments, list) and len(teacher.analytics_assignments) > 0:
                 for assign in teacher.analytics_assignments:
                      subj = assign.get('subject', '').strip()
                      if subject and subject.lower() not in subj.lower():
                           continue
                      if subj and subj != '/' and subj not in teacher_subjects:
                           teacher_subjects.append(subj)
                      if assign.get('classes'):
                           teacher_classes.extend(assign.get('classes'))
            else:
                assignments = TeacherAssignment.objects.filter(teacher=teacher)
                for assign in assignments:
                    if assign.classes:
                        teacher_classes.extend(assign.classes)
                    if assign.subject and assign.subject != '/' and assign.subject not in teacher_subjects:
                        teacher_subjects.append(assign.subject)

            teacher_classes = list(set(teacher_classes))

            if teacher_classes:
                grades_qs = grades_qs.filter(student__class_code__in=teacher_classes)

            if teacher_subjects and not subject:
                import django.db.models as models
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
            import re
            if re.match(r'^\d+م\d+$', class_name):
                grades_qs = grades_qs.filter(student__class_code=class_name)
            else:
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

def get_teacher_assignments_api(request):
    """Returns HR and analytics assignments for a teacher (for analytics modal)."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'غير مصرح'})
    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')
    if not has_access:
        return JsonResponse({'status': 'error', 'message': 'ليس لديك صلاحية'})
    teacher_id = request.GET.get('teacher_id')
    if not teacher_id:
        return JsonResponse({'status': 'error', 'message': 'معرف الأستاذ مطلوب'})
    try:
        from .models import Employee
        emp = Employee.objects.get(id=teacher_id, rank='teacher')
        hr_assignments = list(emp.assignments.all().values('subject', 'classes'))
        analytics_assignments = emp.analytics_assignments if isinstance(emp.analytics_assignments, list) else []
        return JsonResponse({
            'status': 'success',
            'hr_assignments': hr_assignments,
            'analytics_assignments': analytics_assignments,
        })
    except Employee.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'الأستاذ غير موجود'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def save_analytics_teacher_assignment(request):
    """Saves teacher assignment specifically for analytics"""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'غير مصرح'})

    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')

    if not has_access:
        return JsonResponse({'status': 'error', 'message': 'ليس لديك صلاحية'})

    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        assignments_data_raw = request.POST.get('assignments')

        try:
            import json
            from .models import Employee

            emp = Employee.objects.get(id=emp_id)
            if assignments_data_raw is not None:
                assignments_data = json.loads(assignments_data_raw)
                # Filter out empty blocks
                valid_assignments = [a for a in assignments_data if a.get('subject', '').strip() or a.get('classes', [])]
                emp.analytics_assignments = valid_assignments
                emp.save(update_fields=['analytics_assignments'])

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'طلب غير صالح'})


def upload_grades_preview_ajax(request):
    """Parses uploaded grade files and returns unique subjects found to allow user mapping before saving"""
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        term = request.POST.get('term')

        import tempfile
        import os
        from .grade_importer import process_grades_file

        # We need a custom extraction logic here just to get subjects without saving
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            from .import_utils import extract_rows_from_file
            with open(temp_path, 'rb') as f:
                rows = list(extract_rows_from_file(f, override_filename=temp_path))

            if not rows or len(rows) < 7:
                return JsonResponse({'success': False, 'message': 'الملف فارغ أو لا يحتوي على بنية علامات صحيحة'})

            headers = [str(c).strip() for c in rows[5]]

            # Extract subjects using a simplified version of the logic in process_grades_file
            found_subjects = []

            import re
            ignore_exact = {
                'الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب',
                'الجنس', 'النوع', 'تاريخ الميلاد', 'تاريخ الازدياد', 'الميلاد', 'تاريخ'
            }

            for idx, header in enumerate(headers):
                original_header = header.replace('\n', ' ').replace('\r', '').strip()
                clean_header = re.sub(r'(ف|الفصل)\s*\d+', '', original_header).strip()

                # Ignore non-subjects
                if (
                    'اللقب' in clean_header
                    or 'الاسم' in clean_header
                    or 'الإعادة' in clean_header
                    or clean_header in ignore_exact
                    or 'تاريخ الميلاد' in clean_header
                    or 'الجنس' in clean_header
                ):
                    continue

                if len(clean_header) > 2:
                    found_subjects.append(clean_header)

            # Fallback if none found
            if not found_subjects:
                for idx in range(5, min(19, len(headers))):
                    header = headers[idx]
                    original_header = header.replace('\n', ' ').strip()
                    clean_header = re.sub(r'ف\s*\d+', '', original_header).strip()

                    if clean_header and len(clean_header) > 2 and 'اللقب' not in clean_header and 'الاسم' not in clean_header:
                         found_subjects.append(clean_header)

            return JsonResponse({
                'success': True,
                'subjects': list(set(found_subjects)),
                'temp_file': temp_path # Return the path so we can process it in the next step
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"خطأ: {str(e)}"})
        # We don't delete temp_path here because we need it for the actual import

    return JsonResponse({'success': False, 'message': 'طلب غير صالح'})


def rename_subject_ajax(request):
    """Renames an imported subject globally in the Grade table to fix import typos"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})

    # Must be director, superuser, or have access_analytics permission
    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')

    if not has_access:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية لتعديل المواد'})

    if request.method == 'POST':
        old_name = request.POST.get('old_name')
        new_name = request.POST.get('new_name')
        if old_name and new_name:
            from .models import Grade
            from django.db import IntegrityError
            try:
                # If doing a bulk update causes a unique constraint error (e.g. merging two subjects that a student already has both of)
                # we need to handle it gracefully.
                Grade.objects.filter(subject=old_name).update(subject=new_name)
                return JsonResponse({'success': True})
            except IntegrityError:
                return JsonResponse({'success': False, 'error': 'لا يمكن التغيير لوجود علامات مكررة لنفس التلميذ في نفس الفصل تحت هذا الاسم (تعارض). يرجى التأكد أو حذف العلامات المكررة أولاً.'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': False, 'error': 'بيانات مفقودة'})
    return JsonResponse({'success': False, 'error': 'طلب غير صالح'})

def delete_subject_ajax(request):
    """Deletes an imported subject globally from the Grade table"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})

    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')

    if not has_access:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية لحذف المواد'})

    if request.method == 'POST':
        subject_name = request.POST.get('subject_name')
        if subject_name:
            from .models import Grade
            try:
                deleted_count, _ = Grade.objects.filter(subject=subject_name).delete()
                return JsonResponse({'success': True, 'deleted_count': deleted_count})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': False, 'error': 'اسم المادة مفقود'})
    return JsonResponse({'success': False, 'error': 'طلب غير صالح'})


def add_subject_exemption_rule_ajax(request):
    """إضافة قاعدة إعفاء مادة حسب (تلميذ/فوج/مستوى)."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})

    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')
    if not has_access:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طلب غير صالح'})

    subject = (request.POST.get('subject') or '').strip()
    scope_type = (request.POST.get('scope_type') or '').strip()
    term = (request.POST.get('term') or '').strip() or None

    if not subject or scope_type not in ('school', 'student', 'class', 'level'):
        return JsonResponse({'success': False, 'error': 'بيانات غير صحيحة'})

    from .models import SubjectExemptionRule, Student

    rule = SubjectExemptionRule(subject=subject, scope_type=scope_type, term=term)
    if scope_type == 'school':
        # إعفاء بالمؤسسة: لا مدخلات إضافية
        pass
    elif scope_type == 'student':
        student_id_number = (request.POST.get('student_id_number') or '').strip()
        if not student_id_number:
            return JsonResponse({'success': False, 'error': 'رقم تعريف التلميذ مطلوب'})
        try:
            st = Student.objects.get(student_id_number=student_id_number)
        except Student.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'لم يتم العثور على تلميذ بهذا رقم التعريف'})
        rule.student = st
    elif scope_type == 'class':
        class_code = (request.POST.get('class_code') or '').strip()
        if not class_code:
            return JsonResponse({'success': False, 'error': 'رمز الفوج مطلوب'})
        rule.class_code = class_code
    elif scope_type == 'level':
        academic_year = (request.POST.get('academic_year') or '').strip()
        if not academic_year:
            return JsonResponse({'success': False, 'error': 'المستوى مطلوب'})
        rule.academic_year = academic_year

    # منع التكرار البسيط
    exists_q = SubjectExemptionRule.objects.filter(subject=subject, scope_type=scope_type, term=term)
    if scope_type == 'student':
        exists_q = exists_q.filter(student=rule.student)
    elif scope_type == 'class':
        exists_q = exists_q.filter(class_code=rule.class_code)
    else:
        exists_q = exists_q.filter(academic_year=rule.academic_year)
    if exists_q.exists():
        return JsonResponse({'success': True, 'duplicate': True})

    rule.save()
    return JsonResponse({'success': True, 'id': rule.id})


def delete_subject_exemption_rule_ajax(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})

    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')
    if not has_access:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طلب غير صالح'})

    rid = request.POST.get('rule_id')
    if not rid:
        return JsonResponse({'success': False, 'error': 'معرّف القاعدة مفقود'})

    from .models import SubjectExemptionRule
    try:
        SubjectExemptionRule.objects.filter(id=int(rid)).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def save_award_thresholds_ajax(request):
    """حفظ مجالات الإجازات (أدنى معدل فصلي لكل إجازة): امتياز، تهنئة، تشجيع، لوحة شرف."""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مصرح'})
    has_access = request.user.is_superuser or request.user.username == 'director'
    if not has_access and hasattr(request.user, 'profile'):
        has_access = request.user.profile.has_perm('access_analytics')
    if not has_access:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'طلب غير صالح'})
    import json
    keys = ['امتياز', 'تهنئة', 'تشجيع', 'لوحة شرف']
    data = {}
    for k in keys:
        val = request.POST.get('award_' + k)
        if val is not None and str(val).strip() != '':
            try:
                data[k] = float(str(val).strip().replace(',', '.'))
            except ValueError:
                data[k] = 0
        else:
            data[k] = None
    settings_obj = SchoolSettings.objects.first()
    if not settings_obj:
        settings_obj = SchoolSettings.objects.create()
    settings_obj.award_thresholds = data
    settings_obj.save(update_fields=['award_thresholds'])
    return JsonResponse({'success': True, 'award_thresholds': data})


def upload_grades_ajax(request):
    """Handles bulk uploading of multiple grade files with AJAX progress"""
    if request.method == 'POST':
        term = request.POST.get('term')
        import_mode = request.POST.get('import_mode', 'local')
        temp_file_path = request.POST.get('temp_file_path')

        # Load user subject mappings if provided
        import json
        subject_mappings = None
        mappings_json = request.POST.get('subject_mappings')
        if mappings_json:
            try:
                subject_mappings = json.loads(mappings_json)
                # Save these mappings permanently to the database
                from .models_mapping import SubjectAlias
                for old_name, new_name in subject_mappings.items():
                    if new_name and new_name != "ignore":
                        # Create or update alias
                        SubjectAlias.objects.update_or_create(
                            alias=old_name.strip(),
                            defaults={'canonical_name': new_name.strip()}
                        )
            except json.JSONDecodeError:
                pass

        # Load optional teacher<->subjects links (from results subjects, not HR)
        teacher_subject_links = None
        links_json = request.POST.get('teacher_subject_links')
        if links_json:
            try:
                teacher_subject_links = json.loads(links_json) or {}
            except json.JSONDecodeError:
                teacher_subject_links = None

        import tempfile
        import os
        from .grade_importer import process_grades_file, process_grades_file_ai

        temp_path = temp_file_path

        # If a new file is uploaded instead of relying on temp_file_path
        if request.FILES.get('file'):
            file = request.FILES['file']
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                    for chunk in file.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name
            except Exception as e:
                return JsonResponse({'success': False, 'message': f"خطأ في حفظ الملف: {str(e)}", 'count': 0})

        if not temp_path or not os.path.exists(temp_path):
             return JsonResponse({'success': False, 'message': "الملف غير موجود.", 'count': 0})

        try:
            if import_mode == 'ai':
                count, msg = process_grades_file_ai(temp_path, term)
            else:
                count, msg = process_grades_file(temp_path, term, subject_mappings=subject_mappings)

            # بعد اعتماد المواد: تحديث إسناد المواد للأساتذة بناءً على المواد المعتمدة (وليس مواد الموارد البشرية الخام)
            if subject_mappings:
                from .models import Employee, TeacherAssignment
                # نبني خريطة: اسم_قديم -> اسم_معتمد (مع احترام خيار "الاحتفاظ بنفس الاسم")
                normalized_map = {}
                for old_name, new_name in subject_mappings.items():
                    if not old_name:
                        continue
                    if new_name == "ignore":
                        continue
                    # الاحتفاظ بنفس الاسم: نستخدم الاسم كما في الملف
                    canonical = old_name if (new_name in ("--احتفاظ بنفس الاسم--", "", None)) else new_name
                    normalized_map[old_name.strip()] = canonical.strip()

                if normalized_map:
                    # تحديث TeacherAssignment.subject
                    for old_name, canonical in normalized_map.items():
                        TeacherAssignment.objects.filter(subject=old_name).update(subject=canonical)

                    # تحديث analytics_assignments لكل أستاذ بحيث تستعمل نفس أسماء المواد المعتمدة
                    for emp in Employee.objects.exclude(analytics_assignments=None):
                        if not isinstance(emp.analytics_assignments, list):
                            continue
                        changed = False
                        new_assignments = []
                        for a in emp.analytics_assignments or []:
                            subj = (a.get('subject') or '').strip()
                            if subj in normalized_map:
                                a['subject'] = normalized_map[subj]
                                changed = True
                            new_assignments.append(a)
                        if changed:
                            emp.analytics_assignments = new_assignments
                            emp.save(update_fields=['analytics_assignments'])

            # إذا اختار المستخدم ربط الأساتذة بمواد النتائج مباشرة بعد ربط المواد
            if teacher_subject_links and isinstance(teacher_subject_links, dict):
                from .models import Employee, TeacherAssignment
                for tid, payload in teacher_subject_links.items():
                    try:
                        emp = Employee.objects.get(id=int(tid))
                    except Exception:
                        continue
                    subjects = payload.get('subjects') if isinstance(payload, dict) else None
                    if not subjects or not isinstance(subjects, list):
                        continue
                    subjects = [str(s).strip() for s in subjects if str(s).strip()]
                    if not subjects:
                        continue

                    # دمج مع الإسناد الحالي: نحافظ على classes إن وُجدت لنفس المادة
                    existing = {}
                    if isinstance(emp.analytics_assignments, list):
                        for a in emp.analytics_assignments or []:
                            s = (a.get('subject') or '').strip()
                            if not s:
                                continue
                            cl = a.get('classes')
                            existing[s] = list(cl) if isinstance(cl, list) else ([cl] if cl else [])

                    # إذا كانت الأقسام فارغة لمادة ما، نملأها تلقائياً من إسناد الموارد البشرية (حتى لا يلزم حفظ إسناد كل أستاذ يدوياً)
                    def _norm_subj(t):
                        t = (t or '').strip().replace('ـ', '').replace('  ', ' ')
                        if t.startswith('ال'):
                            t = t[2:].strip()
                        return t.lower()

                    hr_assignments = list(TeacherAssignment.objects.filter(teacher=emp).values_list('subject', 'classes'))
                    for subj, classes in hr_assignments:
                        if not subj or str(subj).strip() == '/':
                            continue
                        hr_subj = str(subj).strip()
                        cl_list = list(classes) if isinstance(classes, list) else ([classes] if classes else [])
                        if not cl_list:
                            continue
                        n_hr = _norm_subj(hr_subj)
                        for s in subjects:
                            if existing.get(s):
                                continue
                            n_s = _norm_subj(s)
                            if n_hr in n_s or n_s in n_hr or hr_subj in s or s in hr_subj:
                                existing[s] = list(cl_list)
                                break

                    emp.analytics_assignments = [{'subject': s, 'classes': list(existing.get(s, []))} for s in subjects]
                    emp.save(update_fields=['analytics_assignments'])

            success = count > 0
            return JsonResponse({'success': success, 'message': msg, 'count': count})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"خطأ: {str(e)}", 'count': 0})
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    return JsonResponse({'success': False, 'message': 'طلب غير صالح'})
