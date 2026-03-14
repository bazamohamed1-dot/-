with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

# Replace Grade and Student imports with Historical variants
content = content.replace("from .models import Student, Grade", "from .models import Student, HistoricalStudent, HistoricalGrade")

# Change how we process students:
# We don't try to look up or create in Student anymore, we use HistoricalStudent
import_logic_search = """                    student = None
                    if s_id and s_id.isdigit():
                        student = Student.objects.filter(student_id_number=s_id).first()
                        if not student:
                            # Try with/without .0 just in case
                            student = Student.objects.filter(student_id_number=s_id.replace('.0', '') if '.0' in s_id else s_id + '.0').first()
                    if not student:
                        student = Student.objects.filter(last_name=last_name, first_name=first_name).first()

                    if not student:
                        import random
                        fake_id = s_id if s_id and not s_id.endswith('.0') else (s_id[:-2] if s_id and s_id.endswith('.0') else str(random.randint(10000000, 99999999)))

                        # Use generate_class_code to ensure uniform class_code creation
                        temp_student = Student(academic_year=detected_level or 'أولى متوسط', class_name=detected_class or 'أولى 1')
                        class_code = temp_student.generate_class_code()

                        try:
                            student = Student.objects.create(
                                student_id_number=fake_id,
                                last_name=last_name,
                                first_name=first_name,
                                date_of_birth='2000-01-01',
                                enrollment_date='2000-01-01',
                                academic_year=detected_level or 'أولى متوسط',
                                class_name=detected_class or 'أولى 1',
                                class_code=class_code
                            )
                        except django.db.utils.IntegrityError:
                            # Fallback if UNIQUE constraint fails somehow due to concurrency or edge case
                            student = Student.objects.filter(student_id_number=fake_id).first()
                            if not student:
                                student = Student.objects.create(
                                    student_id_number=fake_id + str(random.randint(10, 99)),
                                    last_name=last_name,
                                    first_name=first_name,
                                    date_of_birth='2000-01-01',
                                    enrollment_date='2000-01-01',
                                    academic_year=detected_level or 'أولى متوسط',
                                    class_name=detected_class or 'أولى 1',
                                    class_code=class_code
                                )"""

import_logic_replace = """                    # --- NEW LOGIC: ONLY IMPORT IF STUDENT CURRENTLY EXISTS IN THE SCHOOL ---
                    # The user requested that we do not import or analyze students who have left the school.
                    current_student = None
                    if s_id and s_id.isdigit():
                        current_student = Student.objects.filter(student_id_number=s_id).first()
                        if not current_student:
                            current_student = Student.objects.filter(student_id_number=s_id.replace('.0', '') if '.0' in s_id else s_id + '.0').first()

                    if not current_student:
                        current_student = Student.objects.filter(last_name=last_name, first_name=first_name).first()

                    # If they are not currently in the school, we skip them entirely
                    if not current_student:
                        continue

                    # Instead of saving to Student, we save to HistoricalStudent
                    student, created = HistoricalStudent.objects.get_or_create(
                        student_id_number=current_student.student_id_number,
                        historical_year=detected_year,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name,
                            'academic_year': detected_level or 'أولى متوسط',
                            'class_name': detected_class or 'أولى 1',
                            'class_code': 'مستورد' # Or potentially calculate it
                        }
                    )"""

content = content.replace(import_logic_search, import_logic_replace)

grade_logic_search = """                                    Grade.objects.update_or_create(
                                        student=student,
                                        subject=subj,
                                        term=term,
                                        academic_year=detected_year,
                                        defaults={'score': score}
                                    )"""

grade_logic_replace = """                                    HistoricalGrade.objects.update_or_create(
                                        student=student,
                                        subject=subj,
                                        term=term,
                                        historical_year=detected_year,
                                        defaults={'score': score}
                                    )"""

content = content.replace(grade_logic_search, grade_logic_replace)

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
