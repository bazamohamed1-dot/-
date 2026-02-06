from rest_framework import viewsets
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Count, F
from django.utils import timezone
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings
from .serializers import StudentSerializer, CanteenAttendanceSerializer, LibraryLoanSerializer, SchoolSettingsSerializer
import openpyxl
from openpyxl.styles import Font, Alignment
from django.http import HttpResponse, HttpResponseForbidden
from datetime import date, timedelta
import os
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

# --- Restore StudentViewSet ---
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            Student.objects.filter(id__in=ids).delete()
            return Response({'message': f'Deleted {len(ids)} students'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Library Views ---

@csrf_exempt
@api_view(['POST'])
def scan_library_card(request):
    barcode = request.data.get('barcode')
    if not barcode:
        return Response({'error': 'No barcode provided'}, status=status.HTTP_400_BAD_REQUEST)

    barcode = str(barcode).strip()
    try:
        # Search by student_id_number
        student = Student.objects.get(student_id_number=barcode)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

    # Get active loans
    active_loans = LibraryLoan.objects.filter(student=student, is_returned=False)

    return Response({
        'student': StudentSerializer(student).data,
        'active_loans': LibraryLoanSerializer(active_loans, many=True).data
    })

@csrf_exempt
@api_view(['POST'])
def create_loan(request):
    student_id = request.data.get('student_id')
    book_title = request.data.get('book_title')
    loan_date_str = request.data.get('loan_date') # Allow manual override

    if not student_id or not book_title:
        return Response({'error': 'Missing data'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    if loan_date_str:
        try:
            loan_date = date.fromisoformat(loan_date_str)
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        loan_date = date.today()

    expected_return = loan_date + timedelta(days=15)

    loan = LibraryLoan.objects.create(
        student=student,
        book_title=book_title,
        loan_date=loan_date,
        expected_return_date=expected_return
    )

    return Response(LibraryLoanSerializer(loan).data, status=status.HTTP_201_CREATED)

@api_view(['GET', 'DELETE'])
def get_readers(request):
    if request.method == 'DELETE':
        # Point 11: Clear history (delete all loans? or just logs? Assuming all loans history)
        # User said "Delete list of readers", which implies clearing the log.
        # Be careful not to delete active loans if that's not intended, but usually "clear history" means all.
        # Let's delete ALL loans.
        count = LibraryLoan.objects.all().delete()[0]
        return Response({'message': f'Deleted {count} records'})

    # Point 12: Include loan date and book title
    # Since a student can have multiple loans, returning "distinct student" hides details.
    # The user wants "When clicking reader list, show loan date and book".
    # This implies listing LOANS, not just unique students.
    loans = LibraryLoan.objects.select_related('student').order_by('-loan_date')
    data = []
    for loan in loans:
        s = loan.student
        data.append({
            'student_id_number': s.student_id_number,
            'first_name': s.first_name,
            'last_name': s.last_name,
            'class_name': s.class_name,
            'book_title': loan.book_title,
            'loan_date': loan.loan_date
        })
    return Response(data)

@csrf_exempt
@api_view(['GET', 'POST'])
def school_settings(request):
    settings_obj = SchoolSettings.objects.first()

    if request.method == 'GET':
        if settings_obj:
            return Response(SchoolSettingsSerializer(settings_obj).data)
        return Response({})

    elif request.method == 'POST':
        if settings_obj:
            serializer = SchoolSettingsSerializer(settings_obj, data=request.data, partial=True)
        else:
            serializer = SchoolSettingsSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        print(f"Settings Save Error: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def return_book(request):
    loan_id = request.data.get('loan_id')
    try:
        loan = LibraryLoan.objects.get(id=loan_id)
    except LibraryLoan.DoesNotExist:
        return Response({'error': 'Loan not found'}, status=status.HTTP_404_NOT_FOUND)

    loan.is_returned = True
    loan.actual_return_date = date.today()
    loan.save()

    return Response({'message': 'Book returned successfully'})

@api_view(['GET'])
def library_stats(request):
    today = date.today()

    # Point 10: Stats Intervals (Daily, Weekly, Monthly, Quarterly, Yearly)
    # Using loan_date as the metric
    daily = LibraryLoan.objects.filter(loan_date=today).count()

    week_start = today - timedelta(days=today.weekday()) # Start of week (Monday?) or just last 7 days? User said "Weekly". Let's do last 7 days.
    # Actually "Weekly" usually means "This Week". But let's stick to simple "Last 7 days" or "This week" depending on interpretation.
    # Let's use "This Week" (since start of week) or rolling 7 days. Rolling 7 is safer.
    weekly = LibraryLoan.objects.filter(loan_date__gte=today - timedelta(days=7)).count()
    monthly = LibraryLoan.objects.filter(loan_date__gte=today - timedelta(days=30)).count()
    quarterly = LibraryLoan.objects.filter(loan_date__gte=today - timedelta(days=90)).count()
    yearly = LibraryLoan.objects.filter(loan_date__gte=today - timedelta(days=365)).count()

    total_students = Student.objects.count()
    borrowers_count = LibraryLoan.objects.values('student').distinct().count()

    percentage = 0
    if total_students > 0:
        percentage = round((borrowers_count / total_students) * 100, 1)

    # Overdue loans: Not returned AND expected_return < today
    overdue_loans = LibraryLoan.objects.filter(
        is_returned=False,
        expected_return_date__lt=today
    ).select_related('student')

    overdue_list = []
    for loan in overdue_loans:
        overdue_list.append({
            'student_name': f"{loan.student.last_name} {loan.student.first_name}",
            'student_class': loan.student.class_name,
            'book_title': loan.book_title,
            'loan_date': loan.loan_date,
            'expected_return': loan.expected_return_date,
            'days_overdue': (today - loan.expected_return_date).days
        })

    return Response({
        'borrowers_count': borrowers_count,
        'borrowers_percentage': percentage,
        'overdue_loans': overdue_list,
        'stats': {
            'daily': daily,
            'weekly': weekly,
            'monthly': monthly,
            'quarterly': quarterly,
            'yearly': yearly
        }
    })

@csrf_exempt
@api_view(['POST'])
def scan_card(request):
    try:
        barcode = request.data.get('barcode')
        print(f"DEBUG: Received barcode: {barcode}") # Simple print for container logs
    except Exception as e:
        print(f"DEBUG: Error parsing data: {e}")
        return Response({'error': 'Invalid JSON data'}, status=status.HTTP_400_BAD_REQUEST)

    if not barcode:
        return Response({'error': 'No barcode provided'}, status=status.HTTP_400_BAD_REQUEST)

    # Clean the barcode (remove spaces, etc)
    barcode = str(barcode).strip()

    try:
        # Assuming barcode matches student_id_number
        student = Student.objects.get(student_id_number=barcode)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

    # Check if Half-Board
    if student.attendance_system != 'نصف داخلي':
        return Response({
            'error': 'Student is not Half-Board',
            'student': StudentSerializer(student).data,
            'code': 'NOT_HALF_BOARD'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if already attended today
    today = date.today()
    if CanteenAttendance.objects.filter(student=student, date=today).exists():
        return Response({
            'error': 'Student already took the meal',
            'student': StudentSerializer(student).data,
            'code': 'ALREADY_ATE'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Record attendance
    attendance = CanteenAttendance.objects.create(student=student, date=today)
    return Response({
        'message': 'Attendance recorded',
        'student': StudentSerializer(student).data,
        'attendance': CanteenAttendanceSerializer(attendance).data
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def get_canteen_stats(request):
    today = date.today()
    total_half_board = Student.objects.filter(attendance_system='نصف داخلي').count()
    present_count = CanteenAttendance.objects.filter(date=today).count()
    absent_count = total_half_board - present_count

    return Response({
        'total_half_board': total_half_board,
        'present_count': present_count,
        'absent_count': max(0, absent_count)
    })

@csrf_exempt
@api_view(['POST'])
def manual_attendance(request):
    student_id = request.data.get('student_id')
    # Can search by internal ID or student_id_number
    try:
        student = Student.objects.get(id=student_id)
    except (Student.DoesNotExist, ValueError):
         try:
            student = Student.objects.get(student_id_number=student_id)
         except Student.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    if student.attendance_system != 'نصف داخلي':
        return Response({'error': 'Student is not Half-Board'}, status=status.HTTP_400_BAD_REQUEST)

    today = date.today()
    if CanteenAttendance.objects.filter(student=student, date=today).exists():
        return Response({'error': 'Student already recorded'}, status=status.HTTP_400_BAD_REQUEST)

    CanteenAttendance.objects.create(student=student, date=today)
    return Response({'message': 'Manual attendance recorded'}, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def get_attendance_lists(request):
    today = date.today()
    present_attendances = CanteenAttendance.objects.filter(date=today).select_related('student')
    present_students = [att.student for att in present_attendances]
    present_ids = [s.id for s in present_students]

    absent_students = Student.objects.filter(attendance_system='نصف داخلي').exclude(id__in=present_ids)

    return Response({
        'present': StudentSerializer(present_students, many=True).data,
        'absent': StudentSerializer(absent_students, many=True).data
    })

@csrf_exempt
@api_view(['POST'])
def export_canteen_sheet(request):
    # This view will update the Excel file in the root/backup folder

    file_path = os.path.join(settings.BASE_DIR, 'Canteen_Attendance.xlsx')
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    try:
        if os.path.exists(file_path):
            wb = openpyxl.load_workbook(file_path)
        else:
            wb = openpyxl.Workbook()
            if 'Sheet' in wb.sheetnames:
                del wb['Sheet']
    except Exception as e:
        return Response({'error': f'Failed to load Excel: {str(e)}'}, status=500)

    sheet_name = "سجل_المطعم"
    if sheet_name not in wb.sheetnames:
        ws = wb.create_sheet(sheet_name)
        ws.append(["التاريخ", "رقم التعريف", "الاسم", "اللقب", "القسم", "الحالة"])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
    else:
        ws = wb[sheet_name]

    # Get data for today
    present_attendances = CanteenAttendance.objects.filter(date=today).select_related('student')
    present_ids = set()

    # Append Present
    for att in present_attendances:
        s = att.student
        present_ids.add(s.id)
        # Check if already in sheet for today (simple check)
        # Optimized: just append for now, or use a set of (date, id) if we read the sheet first.
        # Given request: "Accumulate days".
        ws.append([date_str, s.student_id_number, s.first_name, s.last_name, s.class_name, "حاضر"])

    # Append Absent
    absent_students = Student.objects.filter(attendance_system='نصف داخلي').exclude(id__in=present_ids)
    for s in absent_students:
        ws.append([date_str, s.student_id_number, s.first_name, s.last_name, s.class_name, "غائب"])

    try:
        wb.save(file_path)
    except Exception as e:
        return Response({'error': f'Failed to save Excel: {str(e)}'}, status=500)

    return Response({'message': 'Excel updated successfully', 'file': file_path})

@login_required
def unlock_user(request, user_id):
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'director':
        return HttpResponseForbidden("Access Denied")

    target_user = get_object_or_404(User, id=user_id)
    if hasattr(target_user, 'profile'):
        target_user.profile.is_locked = False
        target_user.profile.failed_attempts = 0
        target_user.profile.save()
        messages.success(request, f"تم فك الحظر عن المستخدم {target_user.username}")

    return redirect('settings')

@login_required
def reset_session(request, user_id):
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'director':
        return HttpResponseForbidden("Access Denied")

    target_user = get_object_or_404(User, id=user_id)
    if hasattr(target_user, 'profile'):
        target_user.profile.active_session_token = None
        target_user.profile.device_fingerprint = None
        target_user.profile.save()
        messages.success(request, f"تمت إعادة تعيين الجلسة للمستخدم {target_user.username}")

    return redirect('settings')

@login_required
def change_user_password(request, user_id):
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'director':
        return HttpResponseForbidden("Access Denied")

    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')

        if new_pass and new_pass == confirm_pass:
            target_user = get_object_or_404(User, id=user_id)
            target_user.set_password(new_pass)
            target_user.save()
            messages.success(request, f"تم تغيير كلمة المرور للمستخدم {target_user.username}")
        else:
            messages.error(request, "كلمات المرور غير متطابقة")

    return redirect('settings')
