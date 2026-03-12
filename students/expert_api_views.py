from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .expert_utils import run_expert_engine
from .models import ExpertAnalysisRun, StudentExpertData, CohortExpertData, SchoolSettings
import threading
from .ai_utils import AIService

@login_required
def api_expert_run(request):
    """
    Triggers the background engine to process data.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            current_year = data.get('current_year', '2024-2025')
            current_term = data.get('current_term', 'الفصل الأول')
            prev_year = data.get('prev_year', '2023-2024')

            # Run in a background thread with proper DB connection cleanup
            def background_task():
                from django.db import connection
                try:
                    run_expert_engine(current_year, current_term, prev_year)
                finally:
                    connection.close()

            thread = threading.Thread(target=background_task)
            thread.start()

            return JsonResponse({'status': 'success', 'message': 'تم بدء تشغيل محرك الخبراء في الخلفية'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def api_expert_data(request):
    """
    Returns the pre-calculated expert data for the dashboard.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    run_id = request.GET.get('run_id')
    level = request.GET.get('level')

    if not run_id:
        latest_run = ExpertAnalysisRun.objects.filter(status='completed').order_by('-run_date').first()
        if not latest_run:
            return JsonResponse({'status': 'error', 'message': 'لا توجد بيانات خبراء معالجة.'}, status=404)
        run_id = latest_run.id

    try:
        run = ExpertAnalysisRun.objects.get(id=run_id)

        # 1. Fetch Students Data
        students_qs = StudentExpertData.objects.filter(run=run)
        if level:
            students_qs = students_qs.filter(academic_year_level__icontains=level)

        students_data = []
        for s in students_qs:
            students_data.append({
                'student_name': s.student.full_name,
                'class_name': s.class_name,
                'level': s.academic_year_level,
                'residual': s.residual,
                'status_pattern': s.status_pattern,
                'current_avg': s.current_avg,
                'predicted_avg': s.predicted_avg,
                'traffic_light': s.traffic_light,
                'net_value_added': s.net_value_added,
                'z_score': s.z_score,
                'trend_history': s.trend_history
            })

        # 2. Fetch Cohort Data
        cohort_qs = CohortExpertData.objects.filter(run=run)
        if level:
            cohort_qs = cohort_qs.filter(academic_year_level__icontains=level)

        cohort_data = []
        for c in cohort_qs:
            cohort_data.append({
                'level': c.academic_year_level,
                'correlation_matrix': c.correlation_matrix,
                'current_year_z_score_avg': c.current_year_z_score_avg,
                'last_year_z_score_avg': c.last_year_z_score_avg,
                'cohort_effect_analysis': c.cohort_effect_analysis,
                'sensitivity_betas': c.sensitivity_betas,
                'ruling_subject': c.ruling_subject
            })

        return JsonResponse({
            'status': 'success',
            'run_info': {
                'id': run.id,
                'date': run.run_date.strftime('%Y-%m-%d %H:%M'),
                'academic_year': run.academic_year,
                'term': run.term
            },
            'students': students_data,
            'cohorts': cohort_data
        })

    except ExpertAnalysisRun.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Run not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def api_expert_generate_report(request):
    """
    Generates AI reports (Diagnostic Report or Meeting Minutes) using AIService.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '')

            if not prompt:
                return JsonResponse({'status': 'error', 'message': 'No prompt provided'}, status=400)

            system_context = """
            أنت خبير تربوي وإحصائي. وظيفتك تحليل البيانات الإحصائية المعقدة الناتجة عن "محرك الخبراء" (Linear Regression, Z-Scores, Heatmap, Beta sensitivity)
            وترجمتها إلى لغة إدارية/تربوية بسيطة ومباشرة موجهة لمدير مؤسسة تعليمية.
            يجب أن تستخلص "المشكلة الجوهرية" و"الخطوة العملية للتدخل" بناءً على الأرقام.
            """

            # Use AIService directly to generate text
            ai = AIService(system_context=system_context)
            response_text = ai.generate_response(prompt)

            return JsonResponse({'status': 'success', 'response': response_text})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def api_expert_available_years(request):
    """
    Returns the count of historical years in the database to reassure the director.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    from .models import Grade
    years = Grade.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    years = [y for y in years if y and y != ""]

    count = len(years)
    years_str = ", ".join(years)

    return JsonResponse({
        'status': 'success',
        'count': count,
        'years': years_str
    })

@login_required
def api_import_historical_expert_data(request):
    """
    Imports historical Excel files with previous years data.
    Supports bulk import (multiple files).
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files:
            return JsonResponse({'status': 'error', 'message': 'لم يتم العثور على ملفات للرفع.'}, status=400)

        from .import_utils import extract_rows_from_file
        from .models import Student, Grade
        import re

        total_students_processed = 0
        total_grades_added = 0
        files_processed = 0
        errors = []

        def fuzzy_match_header(header, possible_matches):
            h = str(header).strip()
            for m in possible_matches:
                if m in h:
                    return 100
            return 0

        for file in files:
            try:
                filename = file.name
                rows = list(extract_rows_from_file(file, override_filename=filename))

                # 1. Extract Metadata (Year, Term, Class)
                year_pattern = r'20\d{2}[-/]20\d{2}'
                class_pattern = r'(أولى|ثانية|ثالثة|رابعة)\s*متوسط\s*\d+'

                detected_year = None
                detected_class = None

                # Try filename first
                m_year = re.search(year_pattern, filename)
                if m_year: detected_year = m_year.group(0).replace('/', '-')
                m_class = re.search(class_pattern, filename)
                if m_class: detected_class = m_class.group(0)

                # Try first 10 rows if missing
                if not detected_year or not detected_class:
                    for row in rows[:10]:
                        row_text = " ".join([str(cell) for cell in row if cell])
                        if not detected_year:
                            m = re.search(year_pattern, row_text)
                            if m: detected_year = m.group(0).replace('/', '-')
                        if not detected_class:
                            m = re.search(class_pattern, row_text)
                            if m: detected_class = m.group(0)

                if not detected_year:
                    errors.append(f"الملف {filename}: لم يتم العثور على السنة الدراسية.")
                    continue

                detected_level = None
                if detected_class:
                    if 'أولى' in detected_class: detected_level = 'أولى متوسط'
                    elif 'ثانية' in detected_class: detected_level = 'ثانية متوسط'
                    elif 'ثالثة' in detected_class: detected_level = 'ثالثة متوسط'
                    elif 'رابعة' in detected_class: detected_level = 'رابعة متوسط'

                # 2. Find Header Row and Subject Columns
                header_row_idx = -1
                subjects_map = {}

                term_map = {
                    'ف1': 'الفصل الأول', 'ف 1': 'الفصل الأول',
                    'ف2': 'الفصل الثاني', 'ف 2': 'الفصل الثاني',
                    'ف3': 'الفصل الثالث', 'ف 3': 'الفصل الثالث'
                }

                for i, row in enumerate(rows[:20]):
                    row_text = " ".join([str(cell) for cell in row if cell])
                    if 'اللقب' in row_text or 'الاسم' in row_text or 'الرقم' in row_text:
                        header_row_idx = i
                        for col_idx, cell in enumerate(row):
                            if not cell: continue
                            val = str(cell).strip()
                            if any(x in val for x in ['اللقب', 'الاسم', 'تاريخ', 'الرقم', 'رقم', 'ملاحظة', 'المعدل']):
                                continue

                            m = re.search(r'(.*?)\s*(ف\s*[123])$', val)
                            if m:
                                subj = m.group(1).strip()
                                raw_term = m.group(2).strip().replace(' ', '')
                                db_term = term_map.get(raw_term, 'الفصل الأول')
                                subjects_map[col_idx] = (subj, db_term)
                            else:
                                subjects_map[col_idx] = (val, 'الفصل الأول')
                        break

                if header_row_idx == -1:
                    errors.append(f"الملف {filename}: لم يتم العثور على عناوين الجدول.")
                    continue

                if not subjects_map:
                    errors.append(f"الملف {filename}: لم يتم العثور على أعمدة المواد.")
                    continue

                # 3. Process Students and Grades
                headers = [str(x).strip() if x else '' for x in rows[header_row_idx]]

                id_col = -1
                ln_col = -1
                fn_col = -1
                for idx, h in enumerate(headers):
                    if fuzzy_match_header(h, ['الرقم', 'رقم تسلسلي', 'رقم وطني']) > 80: id_col = idx
                    if fuzzy_match_header(h, ['اللقب']) > 80: ln_col = idx
                    if fuzzy_match_header(h, ['الاسم']) > 80: fn_col = idx

                file_students = 0
                for row in rows[header_row_idx+1:]:
                    if not any(row): continue

                    s_id = str(row[id_col]).strip() if id_col != -1 and len(row) > id_col and row[id_col] else None
                    last_name = str(row[ln_col]).strip() if ln_col != -1 and len(row) > ln_col and row[ln_col] else ""
                    first_name = str(row[fn_col]).strip() if fn_col != -1 and len(row) > fn_col and row[fn_col] else ""

                    if not last_name and not first_name: continue

                    student = None
                    if s_id and s_id.isdigit():
                        student = Student.objects.filter(student_id_number=s_id).first()
                    if not student:
                        student = Student.objects.filter(last_name=last_name, first_name=first_name).first()

                    if not student:
                        import random
                        fake_id = s_id if s_id else str(random.randint(10000000, 99999999))
                        student = Student.objects.create(
                            student_id_number=fake_id,
                            last_name=last_name,
                            first_name=first_name,
                            date_of_birth='2000-01-01',
                            enrollment_date='2000-01-01',
                            academic_year=detected_level or 'أولى متوسط',
                            class_name=detected_class or 'أولى 1'
                        )

                    file_students += 1

                    for col_idx, (subj, term) in subjects_map.items():
                        if col_idx < len(row):
                            val = row[col_idx]
                            try:
                                score = float(str(val).replace(',', '.'))
                                if 0 <= score <= 20:
                                    Grade.objects.update_or_create(
                                        student=student,
                                        subject=subj,
                                        term=term,
                                        academic_year=detected_year,
                                        defaults={'score': score}
                                    )
                                    total_grades_added += 1
                            except (ValueError, TypeError):
                                pass

                if file_students > 0:
                    total_students_processed += file_students
                    files_processed += 1
                else:
                    errors.append(f"الملف {filename}: لم يتم العثور على بيانات تلاميذ صالحة.")

            except Exception as e:
                errors.append(f"الملف {filename}: حدث خطأ داخلي أثناء المعالجة ({str(e)})")

        if files_processed > 0:
            msg = f"تم استيراد {total_grades_added} علامة لـ {total_students_processed} تلميذ بنجاح من {files_processed} ملف(ات)."
            if errors:
                msg += " \nملاحظة: " + " | ".join(errors)
            return JsonResponse({'status': 'success', 'message': msg})
        else:
            return JsonResponse({'status': 'error', 'message': "فشل الاستيراد.\n" + " \n".join(errors)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
