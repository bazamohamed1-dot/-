from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from .models import Student, CanteenAttendance
from datetime import date
from io import StringIO

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
    students = Student.objects.all().order_by('class_name', 'last_name')[:100] # Limit for perf
    return render(request, 'students/student_list.html', {'students': students})
