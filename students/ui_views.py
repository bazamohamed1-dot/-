from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings, PendingUpdate, Employee, SystemMessage, Survey
from datetime import date
from io import StringIO
import os
import tempfile
from django.conf import settings
import openpyxl

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
                # No known access
                logout(request)
                return redirect('canteen_landing')
        else:
            # No profile (e.g., admin). If not superuser, redirect
            if not request.user.is_superuser:
                logout(request)
                return redirect('canteen_landing')

    except Exception:
        logout(request)
        return redirect('canteen_landing')

    context = {
        'total_students': Student.objects.count(),
        'half_board_count': Student.objects.filter(attendance_system='نصف داخلي').count(),
        'db_status': 'متصل',
        'present_today': CanteenAttendance.objects.filter(date=date.today()).count(),
        'absent_today': Student.objects.filter(attendance_system='نصف داخلي').count() - CanteenAttendance.objects.filter(date=date.today()).count(),
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

            out = StringIO()

            try:
                # Execute the robust command
                call_command('import_eleve', file=temp_path, update_existing=update_existing, stdout=out)

                # Check output for keywords
                result_text = out.getvalue()
                if "Successfully imported" in result_text or "Imported:" in result_text:
                    messages.success(request, f"تمت العملية: {result_text}")
                else:
                    # If it finished but with warnings
                    if not result_text.strip(): result_text = "تمت العملية (لا توجد مخرجات)."
                    messages.warning(request, f"ملاحظات العملية: {result_text}")

            except Exception as e:
                messages.error(request, f"خطأ أثناء التنفيذ: {str(e)}")

        except Exception as e:
            messages.error(request, f"خطأ في الملف: {str(e)}")
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
    context = {
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
        student_ids = request.POST.getlist('student_ids')
        students = Student.objects.filter(id__in=student_ids)
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

def hr_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    # Permission check can be added if we have 'access_hr'

    if request.method == 'POST':
        # Import Logic
        if request.FILES.get('file'):
            file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
                ws = wb.active
                count = 0
                for row in ws.iter_rows(min_row=2, values_only=True): # Skip header
                    if row and row[0]: # Assume Name is col 0
                        Employee.objects.create(
                            full_name=row[0],
                            role=row[1] if len(row)>1 else "Unknown",
                            phone=str(row[2]) if len(row)>2 and row[2] else "",
                            notes=str(row[3]) if len(row)>3 and row[3] else ""
                        )
                        count += 1
                messages.success(request, f"تم استيراد {count} موظف.")
            except Exception as e:
                messages.error(request, f"Error: {e}")
            return redirect('hr_home')

        # Add Logic
        elif request.POST.get('action') == 'add':
            Employee.objects.create(
                full_name=request.POST.get('full_name'),
                role=request.POST.get('role'),
                phone=request.POST.get('phone'),
                notes=request.POST.get('notes')
            )
            messages.success(request, "تمت الإضافة")
            return redirect('hr_home')

    employees = Employee.objects.all().order_by('full_name')
    context = {
        'employees': employees,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/hr.html', context)

def hr_delete(request, pk):
    if not request.user.is_authenticated: return redirect('canteen_landing')
    get_object_or_404(Employee, pk=pk).delete()
    messages.success(request, "تم الحذف")
    return redirect('hr_home')

def parents_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')

    # Just list students with parent info
    # Optimize: only fetch needed fields
    students = Student.objects.only('id', 'first_name', 'last_name', 'guardian_name', 'guardian_phone').all()

    context = {
        'students': students,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/parents.html', context)

def guidance_home(request):
    if not request.user.is_authenticated: return redirect('canteen_landing')

    if request.method == 'POST':
        try:
            Survey.objects.create(
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                target_audience=request.POST.get('target_audience'),
                link=request.POST.get('link')
            )
            messages.success(request, "تم إنشاء الاستبيان")
        except Exception as e:
            messages.error(request, "خطأ في الإنشاء")
        return redirect('guidance_home')

    surveys = Survey.objects.all().order_by('-created_at')
    context = {
        'surveys': surveys,
        'permissions': request.user.profile.permissions if hasattr(request.user, 'profile') else [],
        'is_director': request.user.profile.role == 'director' if hasattr(request.user, 'profile') else request.user.is_superuser
    }
    return render(request, 'students/guidance.html', context)
