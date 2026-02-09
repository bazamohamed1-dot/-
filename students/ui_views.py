from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings, PendingUpdate
from datetime import date
from io import StringIO
import os
import tempfile
from django.conf import settings

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

    # Strict Role Redirection
    try:
        if hasattr(request.user, 'profile'):
            role = request.user.profile.role

            if role == 'librarian':
                return redirect('library_home')
            elif role == 'storekeeper':
                return redirect('canteen_home')
            elif role == 'secretariat':
                return redirect('students_management')
            elif role == 'archivist':
                return redirect('archive_home')
            elif role != 'director':
                # Unknown role or unauthorized
                return redirect('canteen_landing')
            # Director continues
        else:
            # No profile (e.g., admin). If not superuser, redirect
            if not request.user.is_superuser:
                return redirect('canteen_landing')

    except Exception:
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
    # Check import permission
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('import_data'):
         return redirect('dashboard')

    # Checkbox logic
    update_existing = request.POST.get('update_existing') == 'on'

    if request.method == 'POST' and request.FILES.get('eleve_file'):
        eleve_file = request.FILES['eleve_file']
        temp_path = None

        # Use tempfile for safe file handling
        try:
            # Determine suffix from original file
            _, ext = os.path.splitext(eleve_file.name)
            if not ext:
                ext = '.xls' # Default fallback

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in eleve_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            out = StringIO()
            # Call command with Retry Logic for OperationalError
            try:
                from django.db import OperationalError
                try:
                    call_command('import_eleve', file=temp_path, update_existing=update_existing, stdout=out)
                except OperationalError:
                    # Retry once if DB connection failed
                    from django.db import connection
                    connection.close()
                    call_command('import_eleve', file=temp_path, update_existing=update_existing, stdout=out)

                messages.success(request, f"تم الاستيراد بنجاح: {out.getvalue()}")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                messages.error(request, f"فشل الاستيراد: {str(e)} \n التفاصيل: {error_details}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except: pass

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            # Catch file handling errors
            messages.error(request, f"خطأ في معالجة الملف: {str(e)} \n التفاصيل: {error_details}")
            if temp_path and os.path.exists(temp_path):
                 try:
                    os.remove(temp_path)
                 except: pass

        return redirect('settings')

    # Fallback to default behavior if no file uploaded but POST triggered (legacy)
    if request.method == 'POST':
        out = StringIO()
        try:
            call_command('import_eleve', update_existing=update_existing, stdout=out)
            messages.success(request, f"تم الاستيراد بنجاح: {out.getvalue()}")
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء الاستيراد: {str(e)}")
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
