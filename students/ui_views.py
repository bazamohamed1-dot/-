from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.management import call_command
from .models import Student, CanteenAttendance, SchoolSettings
from datetime import date
from io import StringIO
import os
from django.conf import settings

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
    context = {
        'total_students': Student.objects.count(),
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
