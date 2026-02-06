from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings, UserProfile
from datetime import date
from io import StringIO
import os
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
import uuid

def dashboard(request):
    context = {
        'total_students': Student.objects.count(),
        'half_board_count': Student.objects.filter(attendance_system='نصف داخلي').count(),
        'db_status': 'متصل',
        'present_today': CanteenAttendance.objects.filter(date=date.today()).count(),
        'absent_today': Student.objects.filter(attendance_system='نصف داخلي').count() - CanteenAttendance.objects.filter(date=date.today()).count()
    }
    return render(request, 'students/dashboard.html', context)

def settings_view(request):
    users = User.objects.select_related('profile').all()
    context = {
        'total_students': Student.objects.count(),
        'users': users,
    }
    return render(request, 'students/settings.html', context)

def import_eleve_view(request):
    if request.method == 'POST' and request.FILES.get('eleve_file'):
        eleve_file = request.FILES['eleve_file']

        # Save temporary file
        temp_path = os.path.join(settings.BASE_DIR, 'temp_import.xls')
        with open(temp_path, 'wb+') as destination:
            for chunk in eleve_file.chunks():
                destination.write(chunk)

        out = StringIO()
        try:
            # Call command with the temp file path
            call_command('import_eleve', file=temp_path, stdout=out)
            messages.success(request, f"تم الاستيراد بنجاح: {out.getvalue()}")
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء الاستيراد: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return redirect('settings')

    # Fallback to default behavior if no file uploaded but POST triggered (legacy)
    if request.method == 'POST':
        out = StringIO()
        try:
            call_command('import_eleve', stdout=out)
            messages.success(request, f"تم الاستيراد بنجاح: {out.getvalue()}")
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء الاستيراد: {str(e)}")
        return redirect('settings')

    return redirect('settings')

def canteen_home(request):
    # This serves the new Canteen UI which extends base.html
    return render(request, 'students/canteen.html')

def student_list(request):
    # This is the old list view, we are replacing it with the full management UI
    return render(request, 'students/student_list.html')

def students_management(request):
    # The new merged interface
    return render(request, 'students/management.html')

def library_home(request):
    return render(request, 'students/library.html')

def print_student_cards(request):
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

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard') # Or role specific home

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        fingerprint = request.POST.get('fingerprint')

        # Check user existence first to check lock status
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
            return render(request, 'students/login.html')

        if hasattr(user, 'profile'):
            profile = user.profile
            if profile.is_locked:
                messages.error(request, 'الحساب مقفل. يرجى الاتصال بالمدير.')
                return render(request, 'students/login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            profile = user.profile

            # Check Session/Fingerprint
            if profile.active_session_token:
                if profile.device_fingerprint and fingerprint and profile.device_fingerprint != fingerprint:
                    messages.error(request, 'لا يمكن الدخول. الحساب مفتوح في جهاز آخر.')
                    return render(request, 'students/login.html')

            # Success
            profile.failed_attempts = 0

            # Set new session token if not exists or if we want to rotate
            new_token = str(uuid.uuid4())
            profile.active_session_token = new_token
            profile.device_fingerprint = fingerprint
            profile.save()

            request.session['session_token'] = new_token
            auth_login(request, user)

            # Redirect based on role
            role = profile.role
            if role == 'storekeeper':
                return redirect('canteen_home')
            elif role == 'librarian':
                return redirect('library_home')
            elif role == 'archivist':
                return redirect('archive_home')
            elif role == 'secretariat':
                return redirect('students_management')
            else:
                return redirect('dashboard') # Director
        else:
            # Failed attempt
            try:
                user_obj = User.objects.get(username=username)
                profile = user_obj.profile
                profile.failed_attempts += 1
                profile.save()

                if profile.failed_attempts >= 3:
                    profile.is_locked = True
                    profile.save()
                    messages.error(request, 'تم قفل الحساب بسبب تكرار المحاولة الخاطئة 3 مرات. اتصل بالمدير.')
                elif profile.failed_attempts == 2:
                    messages.warning(request, 'تحذير: المحاولة القادمة الخاطئة ستؤدي لقفل الحساب.')
                else:
                    messages.error(request, 'كلمة المرور غير صحيحة.')
            except:
                messages.error(request, 'بيانات الدخول غير صحيحة')

    return render(request, 'students/login.html')

def logout_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
        profile.active_session_token = None
        profile.device_fingerprint = None
        profile.save()

    auth_logout(request)
    return redirect('login')

def archive_home(request):
    return render(request, 'students/archive.html')
