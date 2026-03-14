with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

content = content.replace("student = Student.objects.create(",
                          "try:\n                            student = Student.objects.create(")

content = content.replace("                            class_code=class_code\n                        )",
                          "                            class_code=class_code\n                        )\n                        except django.db.utils.IntegrityError:\n                            # Fallback if UNIQUE constraint fails somehow due to concurrency or edge case\n                            student = Student.objects.filter(student_id_number=fake_id).first()\n                            if not student:\n                                student = Student.objects.create(\n                                    student_id_number=fake_id + str(random.randint(10, 99)),\n                                    last_name=last_name,\n                                    first_name=first_name,\n                                    date_of_birth='2000-01-01',\n                                    enrollment_date='2000-01-01',\n                                    academic_year=detected_level or 'أولى متوسط',\n                                    class_name=detected_class or 'أولى 1',\n                                    class_code=class_code\n                                )")

content = "import django\n" + content

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
