import os
import django
from datetime import date
from tablib import Dataset

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

from students.models import Student
from students.resources import StudentResource
from students.import_utils import parse_student_file

def create_mock_xlsx(filename):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active

    # Headers
    # Based on import_utils.py expectations:
    # 0:ID, 1:Last, 2:First, 3:Gender, 4:DOB, ..., 9:POB, 10:Level, 11:Class, 12:Sys, 13:EnrollNum, 14:EnrollDate
    ws.append([
        "ID", "Last", "First", "Gender", "DOB", "X", "X", "X", "X", "POB", "Level", "Class", "System", "EnrollNum", "EnrollDate"
    ])

    # Data - 3 Students in different classes
    data = [
        ["1001", "Student1", "First1", "M", "2010-01-01", "", "", "", "", "City1", "1AS", "1", "Half", "E001", "2023-09-01"],
        ["1002", "Student2", "First2", "F", "2010-02-02", "", "", "", "", "City2", "1AS", "2", "Half", "E002", "2023-09-01"],
        ["1003", "Student3", "First3", "M", "2009-03-03", "", "", "", "", "City3", "2AS", "1", "Full", "E003", "2023-09-01"],
        ["1004", "Student4", "First4", "F", "2009-04-04", "", "", "", "", "City4", "2AS", "2", "Full", "E004", "2023-09-01"],
    ]

    for row in data:
        ws.append(row)

    wb.save(filename)
    print(f"Created mock file: {filename}")

def run_simulation():
    filename = "mock_students.xlsx"
    create_mock_xlsx(filename)

    print("\n--- Parsing File ---")
    raw_data = parse_student_file(filename)
    print(f"Parsed {len(raw_data)} records.")

    for s in raw_data:
        print(f" - {s['student_id_number']}: {s['last_name']} ({s['class_name']})")

    if not raw_data:
        print("Parsing failed!")
        return

    print("\n--- Importing via Resource ---")
    headers = list(raw_data[0].keys())
    dataset = Dataset(headers=headers)
    for row in raw_data:
        dataset.append([row[h] for h in headers])

    resource = StudentResource()
    result = resource.import_data(dataset, dry_run=False, raise_errors=True)

    print(f"Import Result: New={result.totals.get('new')}, Update={result.totals.get('update')}, Skip={result.totals.get('skip')}")

    print("\n--- Verifying DB ---")
    count = Student.objects.filter(student_id_number__in=["1001", "1002", "1003", "1004"]).count()
    print(f"Found {count}/4 mock students in DB.")

    # Cleanup
    if os.path.exists(filename):
        os.remove(filename)

    # Clean DB
    Student.objects.filter(student_id_number__in=["1001", "1002", "1003", "1004"]).delete()

if __name__ == "__main__":
    run_simulation()
