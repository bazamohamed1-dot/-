from rest_framework import viewsets
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count, F
from django.utils import timezone
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, EmployeeProfile
from .serializers import StudentSerializer, CanteenAttendanceSerializer, LibraryLoanSerializer, SchoolSettingsSerializer, ArchiveDocumentSerializer
import openpyxl
from openpyxl.styles import Font, Alignment
from django.http import HttpResponse, FileResponse
from datetime import date, timedelta
import os
from io import BytesIO
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging
from datetime import date

logger = logging.getLogger(__name__)

# --- Restore StudentViewSet ---
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('student_add'):
             return Response({'error': 'Unauthorized'}, status=403)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('student_edit'):
             return Response({'error': 'Unauthorized'}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('student_delete'):
             return Response({'error': 'Unauthorized'}, status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('student_delete'):
             return Response({'error': 'Unauthorized'}, status=403)

        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            Student.objects.filter(id__in=ids).delete()
            return Response({'message': f'Deleted {len(ids)} students'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Lightweight JSON Import API ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students_json(request):
    """
    Receives a JSON list of students and performs bulk create/update.
    This avoids server-side file parsing memory overhead.
    """
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('import_data'):
         return Response({'error': 'Unauthorized'}, status=403)

    data = request.data
    students_list = data.get('students', [])
    update_existing = data.get('update_existing', False)

    if not students_list:
        return Response({'error': 'No data provided'}, status=400)

    created_count = 0
    updated_count = 0
    errors = []

    # Map existing students for fast lookup
    existing_map = {s.student_id_number: s for s in Student.objects.all()}

    to_create = []
    to_update = []

    for item in students_list:
        try:
            sid = str(item.get('student_id_number')).strip()
            if not sid: continue

            # Date parsing fallback
            dob = item.get('date_of_birth')
            if not dob or str(dob).lower() == 'invalid date': dob = '1900-01-01'

            enroll_date = item.get('enrollment_date')
            if not enroll_date or str(enroll_date).lower() == 'invalid date': enroll_date = date.today()

            student_data = {
                'student_id_number': sid,
                'last_name': item.get('last_name', ''),
                'first_name': item.get('first_name', ''),
                'gender': item.get('gender', ''),
                'date_of_birth': dob,
                'place_of_birth': item.get('place_of_birth', ''),
                'academic_year': item.get('academic_year', ''),
                'class_name': item.get('class_name', ''),
                'attendance_system': item.get('attendance_system', ''),
                'enrollment_number': item.get('enrollment_number', ''),
                'enrollment_date': enroll_date,
                'guardian_name': item.get('guardian_name', ''),
                'mother_name': item.get('mother_name', ''),
                'address': item.get('address', ''),
                'guardian_phone': item.get('guardian_phone', ''),
            }

            if sid in existing_map:
                if update_existing:
                    s = existing_map[sid]
                    for key, val in student_data.items():
                        if key != 'student_id_number': # Don't update PK
                            setattr(s, key, val)
                    to_update.append(s)
            else:
                to_create.append(Student(**student_data))

        except Exception as e:
            errors.append(f"Row error: {str(e)}")

    try:
        if to_create:
            Student.objects.bulk_create(to_create)
            created_count = len(to_create)

        if to_update:
            Student.objects.bulk_update(to_update, [
                'last_name', 'first_name', 'gender', 'date_of_birth', 'place_of_birth',
                'academic_year', 'class_name', 'attendance_system', 'enrollment_number',
                'enrollment_date', 'guardian_name', 'mother_name', 'address', 'guardian_phone'
            ])
            updated_count = len(to_update)

        return Response({
            'created': created_count,
            'updated': updated_count,
            'errors': errors
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

class ArchiveDocumentViewSet(viewsets.ModelViewSet):
    queryset = ArchiveDocument.objects.all().order_by('-entry_date')
    serializer_class = ArchiveDocumentSerializer

    @action(detail=False, methods=['post'])
    def export_excel(self, request):
        file_path = os.path.join(settings.BASE_DIR, 'Archive_Export.xlsx')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "أرشيف المؤسسة"

        headers = ["الرقم", "المصلحة", "الملف/السجل", "الوثيقة", "الرمز", "تاريخ الازدياد", "تاريخ الدخول", "تاريخ الخروج المؤقت", "تاريخ الحذف", "ملاحظات"]
        ws.append(headers)

        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        docs = self.filter_queryset(self.get_queryset())
        for doc in docs:
            ws.append([
                doc.reference_number,
                doc.service,
                doc.file_type,
                doc.document_type,
                doc.symbol or '',
                str(doc.student_dob) if doc.student_dob else '',
                str(doc.entry_date),
                str(doc.temp_exit_date) if doc.temp_exit_date else '',
                str(doc.elimination_date) if doc.elimination_date else '',
                doc.notes or ''
            ])

        wb.save(file_path)
        response = FileResponse(open(file_path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Archive_{date.today()}.xlsx"'
        return response

# --- Library Views ---

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_library_card(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('library_scan'):
        return Response({'error': 'Unauthorized'}, status=403)
    try:
        barcode = request.data.get('barcode')
        if not barcode:
            return Response({'error': 'No barcode provided'}, status=status.HTTP_400_BAD_REQUEST)

        barcode = str(barcode).strip()

        # Robust lookup
        try:
            student = Student.objects.get(student_id_number=barcode)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        except Student.MultipleObjectsReturned:
            # Fallback: take the first one or error out. Usually shouldn't happen with ID.
            student = Student.objects.filter(student_id_number=barcode).first()
            if not student:
                 return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

        # Get active loans
        active_loans = LibraryLoan.objects.filter(student=student, is_returned=False)

        # Check limit
        settings_obj = SchoolSettings.objects.first()
        limit = settings_obj.loan_limit if settings_obj else 2
        limit_reached = active_loans.count() >= limit

        return Response({
            'student': StudentSerializer(student).data,
            'active_loans': LibraryLoanSerializer(active_loans, many=True).data,
            'limit_reached': limit_reached,
            'loan_limit': limit
        })
    except Exception as e:
        logger.error(f"Library Scan Error: {e}")
        return Response({'error': f'Server Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_loan(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('library_loan'):
        return Response({'error': 'Unauthorized'}, status=403)
    student_id = request.data.get('student_id')
    book_title = request.data.get('book_title')
    loan_date_str = request.data.get('loan_date') # Allow manual override

    if not student_id or not book_title:
        return Response({'error': 'Missing data'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    # Check loan limit
    active_loans_count = LibraryLoan.objects.filter(student=student, is_returned=False).count()
    settings_obj = SchoolSettings.objects.first()
    limit = settings_obj.loan_limit if settings_obj else 2

    if active_loans_count >= limit:
        return Response({'error': f'لا يمكن استعارة أكثر من {limit} كتب'}, status=status.HTTP_400_BAD_REQUEST)

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
@permission_classes([IsAuthenticated])
def get_readers(request):
    if request.method == 'DELETE':
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('library_readers_list'):
             return Response({'error': 'Unauthorized'}, status=403)

        count = LibraryLoan.objects.all().delete()[0]
        return Response({'message': f'Deleted {count} records'})

    # Point 12: Include loan date and book title
    # Since a student can have multiple loans, returning "distinct student" hides details.
    # The user wants "When clicking reader list, show loan date and book".
    # This implies listing LOANS, not just unique students.
    loans = LibraryLoan.objects.select_related('student').order_by('-loan_date', '-loan_time')
    data = []
    for loan in loans:
        s = loan.student
        data.append({
            'student_id_number': s.student_id_number,
            'first_name': s.first_name,
            'last_name': s.last_name,
            'class_name': s.class_name,
            'book_title': loan.book_title,
            'loan_date': loan.loan_date,
            'loan_time': loan.loan_time.strftime("%H:%M:%S") if loan.loan_time else ""
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
@permission_classes([IsAuthenticated])
def return_book(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('library_return'):
        return Response({'error': 'Unauthorized'}, status=403)

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

    # Distribution stats
    class_dist = LibraryLoan.objects.values('student__class_name').annotate(count=Count('student', distinct=True)).order_by('student__class_name')
    level_dist = LibraryLoan.objects.values('student__academic_year').annotate(count=Count('student', distinct=True)).order_by('student__academic_year')

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
        },
        'class_distribution': list(class_dist),
        'level_distribution': list(level_dist)
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_card(request):
    try:
        # Check permission
        if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('canteen_scan'):
             return Response({'error': 'Unauthorized'}, status=403)

        barcode = request.data.get('barcode')
        logger.info(f"DEBUG: Received barcode: {barcode}")

        if not barcode:
            return Response({'error': 'No barcode provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Clean the barcode (remove spaces, etc)
        barcode = str(barcode).strip()

        # Robust lookup
        try:
            student = Student.objects.get(student_id_number=barcode)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        except Student.MultipleObjectsReturned:
            student = Student.objects.filter(student_id_number=barcode).first()
            if not student:
                return Response({'error': 'Student not found', 'code': 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

        # Time Restriction Logic (13:15)
        now = timezone.localtime()
        cutoff_time = now.replace(hour=13, minute=15, second=0, microsecond=0)

        # Only Director can bypass time limit
        is_director = request.user.profile.role == 'director'

        if now.time() > cutoff_time.time() and not is_director:
             today = date.today()
             attended = CanteenAttendance.objects.filter(student=student, date=today).exists()
             student_data = StudentSerializer(student).data
             if attended:
                 return Response({
                     'error': 'انتهى الوقت (أكل مسبقاً)',
                     'code': 'LATE_ATE',
                     'student': student_data
                 }, status=status.HTTP_403_FORBIDDEN)
             else:
                 return Response({
                     'error': 'انتهى الوقت (لم يأكل)',
                     'code': 'LATE_NOT_ATE',
                     'student': student_data
                 }, status=status.HTTP_403_FORBIDDEN)

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

    except Exception as e:
        logger.error(f"Canteen Scan Error: {e}")
        return Response({'error': f'Server Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_canteen_stats(request):
    today = date.today()
    total_half_board = Student.objects.filter(attendance_system='نصف داخلي').count()
    present_count = CanteenAttendance.objects.filter(date=today).count()

    # User requirement: If no one registered yet (or holiday), don't mark everyone as absent.
    if present_count == 0:
        absent_count = 0
    else:
        absent_count = total_half_board - present_count

    return Response({
        'total_half_board': total_half_board,
        'present_count': present_count,
        'absent_count': max(0, absent_count)
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_attendance(request):
    # Check permission
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('canteen_manual'):
        return Response({'error': 'Unauthorized'}, status=403)

    # Time Restriction Logic (13:15)
    now = timezone.localtime()
    cutoff_time = now.replace(hour=13, minute=15, second=0, microsecond=0)

    # Check if user is director
    is_director = request.user.profile.role == 'director'

    if now.time() > cutoff_time.time() and not is_director:
            return Response({'error': 'انتهى وقت الإطعام (13:15)'}, status=status.HTTP_403_FORBIDDEN)

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

    present_data = []
    present_ids = []
    for att in present_attendances:
        s_data = StudentSerializer(att.student).data
        s_data['attendance_time'] = att.time.strftime("%H:%M:%S")
        present_data.append(s_data)
        present_ids.append(att.student.id)

    absent_students = Student.objects.filter(attendance_system='نصف داخلي').exclude(id__in=present_ids)

    return Response({
        'present': present_data,
        'absent': StudentSerializer(absent_students, many=True).data
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_canteen_sheet(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.has_perm('canteen_export'):
        return Response({'error': 'Unauthorized'}, status=403)

    # Generates a cumulative report in-memory from DB history
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    # Get All History (Optimized)
    # We want to export the log of attendance.
    # If the user wants "Absent" records for past days, we'd need to generate them (since we only store presence).
    # However, usually "Canteen Log" implies who ate.
    # The prompt said: "Save attendance list... accumulate days".
    # So we export all `CanteenAttendance` records.

    all_attendance = CanteenAttendance.objects.select_related('student').order_by('-date', 'student__class_name')

    if not all_attendance.exists():
         return Response({'message': 'لا يوجد سجلات حضور لتصديرها'}, status=status.HTTP_200_OK)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "سجل_المطعم_التراكمي"
    ws.append(["التاريخ", "التوقيت", "رقم التعريف", "الاسم", "اللقب", "القسم", "الحالة"])

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    for att in all_attendance:
        s = att.student
        time_str = att.time.strftime("%H:%M:%S")
        ws.append([str(att.date), time_str, s.student_id_number, s.first_name, s.last_name, s.class_name, "حاضر"])

    # Save to memory buffer
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = FileResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Canteen_Attendance_Full_{date_str}.xlsx"'
    return response
