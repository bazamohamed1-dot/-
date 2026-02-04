from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count
from django.utils import timezone
from .models import Student, CanteenAttendance
from .serializers import StudentSerializer, CanteenAttendanceSerializer
import openpyxl
from openpyxl.styles import Font, Alignment
from django.http import HttpResponse
from datetime import date
import os
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)

# --- Restore StudentViewSet ---
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

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
