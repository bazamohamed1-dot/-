import django
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from .expert_utils import run_expert_engine
from .models import ExpertAnalysisRun, StudentExpertData, CohortExpertData, SchoolSettings
import threading
from .ai_utils import AIService

EXPERT_ENGINE_RUNNING_KEY = 'expert_engine_running'

@login_required
def api_expert_run(request):
    """
    Triggers the background engine to process data.
    Sets cache key so frontend can poll run status.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        import json
        try:
            from .school_year_utils import get_current_school_year, get_prev_school_year, get_school_year_before_prev
            data = json.loads(request.body) if request.body else {}
            current_year = data.get('current_year') or get_current_school_year()
            current_term = data.get('current_term', 'الفصل الأول')
            prev_year = data.get('prev_year') or get_prev_school_year(current_year)
            year_before_prev = get_school_year_before_prev(current_year)
            prev_years_extra = [year_before_prev] if year_before_prev and year_before_prev != prev_year else []

            def background_task():
                from django.db import connection
                try:
                    cache.set(EXPERT_ENGINE_RUNNING_KEY, True, timeout=600)
                    run_expert_engine(current_year, current_term, prev_year, prev_years_extra=prev_years_extra)
                finally:
                    connection.close()
                    cache.delete(EXPERT_ENGINE_RUNNING_KEY)

            thread = threading.Thread(target=background_task)
            thread.start()

            return JsonResponse({'status': 'success', 'message': 'تم بدء تشغيل محرك الخبراء في الخلفية'})
        except Exception as e:
            cache.delete(EXPERT_ENGINE_RUNNING_KEY)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def api_expert_run_status(request):
    """استعلام دوري: هل المحرك قيد التشغيل + آخر تشغيلة."""
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    running = cache.get(EXPERT_ENGINE_RUNNING_KEY, False)
    latest = ExpertAnalysisRun.objects.filter(status='completed').order_by('-run_date').first()
    last_run = None
    if latest:
        last_run = {
            'id': latest.id,
            'run_date': latest.run_date.strftime('%Y-%m-%d %H:%M'),
            'term': latest.term,
            'academic_year': latest.academic_year,
        }
    return JsonResponse({
        'status': 'success',
        'running': bool(running),
        'last_run': last_run,
    })


@login_required
def api_expert_data(request):
    """
    Returns the pre-calculated expert data for the dashboard.
    """
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
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
                'student_id': (s.student_id if s.student else None),
                'student_name': (s.student.full_name if s.student else '—'),
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
                'last_year_raw_avg': getattr(c, 'last_year_raw_avg', None),
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
def api_expert_student_term_grades(request):
    """تفاصيل علامات تلميذ (السنة الحالية/فصل التشغيلة) لمختبر المحاكاة What-If."""
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    try:
        student_id = request.GET.get('student_id')
        run_id = request.GET.get('run_id')
        if not student_id:
            return JsonResponse({'status': 'error', 'message': 'student_id is required'}, status=400)

        run = None
        if run_id:
            run = ExpertAnalysisRun.objects.filter(id=int(run_id)).first()
        if not run:
            run = ExpertAnalysisRun.objects.filter(status='completed').order_by('-run_date').first()
        if not run:
            return JsonResponse({'status': 'error', 'message': 'لا توجد تشغيلة خبراء مكتملة.'}, status=404)

        from .models import Student, Grade
        from .import_utils import standardize_subject_name

        st = Student.objects.filter(id=int(student_id)).first()
        if not st:
            return JsonResponse({'status': 'error', 'message': 'Student not found'}, status=404)

        level_raw = (st.academic_year or '').strip()

        def _normalize_level_key(v):
            s = str(v or '').strip()
            s = ' '.join(s.split())
            if not s:
                return s
            if 'متوسط' not in s and (s.isdigit() and s in {'1', '2', '3', '4'}):
                s = f"{s} متوسط"
            for d, w in (('1', 'أولى'), ('2', 'ثانية'), ('3', 'ثالثة'), ('4', 'رابعة')):
                if s.startswith(d):
                    s = f"{w} متوسط"
                    break
            for w in ('أولى', 'ثانية', 'ثالثة', 'رابعة'):
                if s.startswith(w) and 'متوسط' not in s:
                    s = f"{w} متوسط"
                    break
            return s

        level = _normalize_level_key(level_raw)
        settings = SchoolSettings.objects.order_by('-id').first()
        coefs_by_level = getattr(settings, 'subject_coefficients_by_level', {}) if settings else {}
        if isinstance(coefs_by_level, str):
            try:
                coefs_by_level = json.loads(coefs_by_level) or {}
            except Exception:
                coefs_by_level = {}

        coefs_raw = {}
        if isinstance(coefs_by_level, dict):
            coefs_raw = coefs_by_level.get(level_raw) or coefs_by_level.get(level) or {}
            if not coefs_raw:
                # حاول مفاتيح مطبّعة لتفادي اختلاف تسمية المستوى
                for k, v in coefs_by_level.items():
                    if _normalize_level_key(k) == level:
                        coefs_raw = v or {}
                        break

        # توحيد مفاتيح المواد لتطابق standardize_subject_name
        coefs = {}
        if isinstance(coefs_raw, dict):
            for k, v in coefs_raw.items():
                kk = standardize_subject_name(k) or (str(k).strip() if k is not None else '')
                if not kk:
                    continue
                try:
                    coefs[kk] = float(v)
                except Exception:
                    coefs[kk] = 1.0

        # Pull actual term grades used by the run (effective_term stored in run.term)
        qs = Grade.objects.filter(student=st, academic_year=run.academic_year, term=run.term).values('subject', 'score')
        rows = []
        excel_avg = None
        excel_avg_label = None
        for r in qs:
            subj_raw = (r.get('subject') or '').strip()
            if not subj_raw:
                continue
            if subj_raw.startswith('معدل') or subj_raw.startswith('المعدل'):
                # احتفظ بالمعدل الجاهز من الملف (إن وجد) كمعدل مرجعي مطابق للجدول
                try:
                    excel_avg = float(r.get('score'))
                    excel_avg_label = subj_raw
                except Exception:
                    pass
                continue
            subj = standardize_subject_name(subj_raw) or subj_raw
            score = r.get('score')
            if score is None:
                continue
            # نفس سلوك المحرك: تجاهل الغياب/الصفر/السالب
            try:
                score_f = float(score)
            except Exception:
                continue
            if score_f <= 0:
                continue
            rows.append({'subject': subj, 'score': score_f})

        # Deduplicate subjects after standardization (keep last)
        by_subj = {}
        for r in rows:
            by_subj[r['subject']] = r
        rows = list(by_subj.values())

        # Compute weighted average using coefficients (default 1)
        total = 0.0
        wsum = 0.0
        for r in rows:
            w = float(coefs.get(r['subject'], 1.0)) if isinstance(coefs, dict) else 1.0
            total += float(r['score']) * w
            wsum += w
            r['coef'] = w
        computed_avg = (total / wsum) if wsum > 0 else (sum([r['score'] for r in rows]) / len(rows) if rows else None)
        # استعمل معدل Excel إن وُجد (ليطابق الجدول)، وإلا ارجع للمعدل المحسوب
        current_avg = excel_avg if excel_avg is not None else computed_avg

        return JsonResponse({
            'status': 'success',
            'run': {'id': run.id, 'academic_year': run.academic_year, 'term': run.term},
            'student': {'id': st.id, 'name': st.full_name, 'level': level},
            'coefficients': coefs,
            'subjects': sorted(rows, key=lambda x: x['subject']),
            'current_avg': current_avg,
            'current_avg_source': ('excel' if excel_avg is not None else 'computed'),
            'current_avg_source_label': excel_avg_label,
            'total_coef': wsum,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def api_expert_generate_report(request):
    """
    Generates AI reports (Diagnostic Report or Meeting Minutes) using AIService.
    """
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method == 'POST':
        import json
        try:
            from .school_year_utils import get_current_school_year, get_prev_school_year, get_school_year_before_prev
            data = json.loads(request.body)
            prompt = data.get('prompt', '')
            report_type = (data.get('report_type') or '').strip()  # optional: diagnostic | minutes
            run_id = data.get('run_id')

            if not prompt:
                return JsonResponse({'status': 'error', 'message': 'No prompt provided'}, status=400)

            # اجلب بيانات حقيقية من قاعدة البيانات (تشغيلة + عينات) لبناء تقرير واقعي
            current_year = get_current_school_year()
            prev_year = get_prev_school_year(current_year)
            prev_before = get_school_year_before_prev(current_year)

            run = None
            if run_id:
                try:
                    run = ExpertAnalysisRun.objects.get(id=int(run_id))
                except Exception:
                    run = None
            if not run:
                run = ExpertAnalysisRun.objects.filter(status='completed').order_by('-run_date').first()

            if not run:
                return JsonResponse({'status': 'error', 'message': 'لا توجد تشغيلة مكتملة للمحرك بعد. شغّل المحرك أولاً.'}, status=400)

            # عينات موجّهة: أسوأ/أفضل بواقي + أشد إنذار/أفضل توقع + أعلى Z
            students_qs = StudentExpertData.objects.filter(run=run).exclude(student__isnull=True)
            sample_low = list(students_qs.order_by('predicted_avg')[:8].values('student__last_name', 'student__first_name', 'academic_year_level', 'class_name', 'current_avg', 'predicted_avg', 'residual', 'traffic_light', 'status_pattern'))
            sample_high = list(students_qs.order_by('-predicted_avg')[:8].values('student__last_name', 'student__first_name', 'academic_year_level', 'class_name', 'current_avg', 'predicted_avg', 'residual', 'traffic_light', 'status_pattern'))
            sample_resid_neg = list(students_qs.order_by('residual')[:8].values('student__last_name', 'student__first_name', 'academic_year_level', 'class_name', 'current_avg', 'predicted_avg', 'residual', 'traffic_light', 'status_pattern'))
            sample_resid_pos = list(students_qs.order_by('-residual')[:8].values('student__last_name', 'student__first_name', 'academic_year_level', 'class_name', 'current_avg', 'predicted_avg', 'residual', 'traffic_light', 'status_pattern'))

            cohorts_qs = CohortExpertData.objects.filter(run=run)
            cohort_rows = list(cohorts_qs.values('academic_year_level', 'ruling_subject', 'current_year_z_score_avg', 'last_year_raw_avg', 'cohort_effect_analysis'))

            # ملخصات رقمية بسيطة
            total_students = students_qs.count()
            tl_red = students_qs.filter(traffic_light='red').count()
            tl_yellow = students_qs.filter(traffic_light='yellow').count()
            tl_green = students_qs.filter(traffic_light='green').count()

            system_context = f"""
أنت خبير إحصائي تربوي. اجعل التقرير غالبًا مبنيًا على البيانات (أرقام/نِسَب/أمثلة من التلاميذ والأفواج)، لكن اسمح بقدر محدود من لغة تربوية/إدارية لتفسير النتائج دون جمود.
ممنوع اختلاق أرقام أو أمثلة خارج قاعدة بيانات التطبيق. إذا احتجت تقديرًا أو تفسيرًا عامًا، صرّح أنه تفسير محتمل وليس حقيقة رقمية.

السياق:
- السنة الحالية (من الإعدادات): {current_year}
- للمقارنة: {prev_year} و {prev_before}
- التشغيلة: id={run.id} | السنة={run.academic_year} | الفصل={run.term} | التاريخ={run.run_date}

إحصائيات سريعة:
- عدد التلاميذ في التشغيلة: {total_students}
- إشارات المرور: أحمر={tl_red}, أصفر={tl_yellow}, أخضر={tl_green}

بيانات الأفواج (CohortExpertData):
{json.dumps(cohort_rows, ensure_ascii=False)}

عينات تلاميذ (StudentExpertData):
- أقل توقعًا: {json.dumps(sample_low, ensure_ascii=False)}
- أعلى توقعًا: {json.dumps(sample_high, ensure_ascii=False)}
- أكبر تراجع عن التوقع (Residual سلبي): {json.dumps(sample_resid_neg, ensure_ascii=False)}
- أكبر قفزة عن التوقع (Residual إيجابي): {json.dumps(sample_resid_pos, ensure_ascii=False)}

تعليمات الإخراج:
- اجعل كل نقطة قرار مرتبطة برقم/نسبة أو مثال من العينات عند الإمكان.
- إن كان المطلوب 'تقرير تشخيصي' أعط: تشخيصات رقمية + تفسير تربوي مختصر + أسباب محتملة مرتبطة بالبيانات + توصيات عملية قابلة للتنفيذ + مؤشرات متابعة (KPIs) للفصل القادم.
- إن كان المطلوب 'محضر اجتماع' أعط: جدول أعمال، نقاط قرار، إجراءات، مسؤوليات، آجال، ومؤشرات قياس، مع أمثلة واقعية من العينات.
"""
            ai = AIService()
            response_text = ai.generate_response(system_context, prompt, rag_enabled=False)

            return JsonResponse({'status': 'success', 'response': response_text})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def api_expert_get_subject_coefficients(request):
    """إرجاع معاملات المواد حسب المستوى + أسماء المواد (نفس قائمة لوحة التحليل، بدون تكرار)."""
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    from .import_utils import get_deduplicated_subjects_from_grades
    settings = SchoolSettings.objects.first()
    coefs = getattr(settings, 'subject_coefficients_by_level', None) or {}
    subjects_list = get_deduplicated_subjects_from_grades()
    return JsonResponse({'status': 'success', 'coefficients': coefs, 'subjects': subjects_list})


@login_required
def api_expert_save_subject_coefficients(request):
    """حفظ معاملات المواد حسب المستوى. Body: {"coefficients": {"أولى متوسط": {"الرياضيات": 2, ...}, ...}}"""
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    import json
    try:
        data = json.loads(request.body)
        coefs = data.get('coefficients')
        if not isinstance(coefs, dict):
            return JsonResponse({'status': 'error', 'message': 'يجب أن يكون coefficients كائناً (مستوى -> مواد -> معامل)'}, status=400)
        settings = SchoolSettings.objects.first()
        if not settings:
            settings = SchoolSettings.objects.create()
        settings.subject_coefficients_by_level = coefs
        settings.save()
        return JsonResponse({'status': 'success', 'message': 'تم حفظ معاملات المواد.'})
    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'message': 'صيغة JSON غير صالحة: ' + str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_expert_available_years(request):
    """
    Returns the count of historical years in the database to reassure the director.
    """
    if not getattr(request.user, 'profile', None) or not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    from .models import HistoricalGrade
    years = HistoricalGrade.objects.values_list('historical_year', flat=True).distinct().order_by('-historical_year')
    years = [y for y in years if y and y != ""]

    count = len(years)
    years_str = ", ".join(years)

    return JsonResponse({
        'status': 'success',
        'count': count,
        'years': years_str
    })


@login_required
def api_expert_imported_files_by_year(request):
    """قائمة السنوات الدراسية مع الملفات المستوردة لكل سنة (لعرضها في تبويب قاعدة البيانات)."""
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    from .models import HistoricalImportFile, HistoricalGrade, HistoricalStudent
    from django.db.models import Count

    # السنوات التي لديها ملفات مستوردة
    file_records = list(
        HistoricalImportFile.objects.values('historical_year')
        .annotate(c=Count('id'))
        .order_by('-historical_year')
    )
    years_with_files = [r['historical_year'] for r in file_records if r['historical_year']]

    # إن لم يكن هناك سجل ملفات، نستنتج السنوات من HistoricalGrade
    if not years_with_files:
        years_with_files = list(
            HistoricalGrade.objects.values_list('historical_year', flat=True)
            .distinct().order_by('-historical_year')
        )
        years_with_files = [y for y in years_with_files if y]

    result = []
    for year in years_with_files:
        files = list(
            HistoricalImportFile.objects.filter(historical_year=year)
            .order_by('-imported_at')
            .values('filename', 'imported_at')
        )
        for f in files:
            if f.get('imported_at'):
                f['imported_at'] = f['imported_at'].strftime('%Y-%m-%d %H:%M')
        student_count = HistoricalStudent.objects.filter(historical_year=year).count()
        grade_count = HistoricalGrade.objects.filter(historical_year=year).count()
        result.append({
            'year': year,
            'files': files,
            'student_count': student_count,
            'grade_count': grade_count,
        })

    return JsonResponse({'status': 'success', 'years': result})


@login_required
def api_expert_historical_year_content(request):
    """إرجاع محتوى قاعدة البيانات لسنة سابقة: قائمة التلاميذ وعينة العلامات (للعرض في تبويب قاعدة البيانات)."""
    if not request.user.profile.has_perm('access_analytics'):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    from .models import HistoricalStudent, HistoricalGrade

    year = (request.GET.get('year') or '').strip()
    if not year:
        return JsonResponse({'status': 'error', 'message': 'المعامل year مطلوب'}, status=400)

    students_qs = HistoricalStudent.objects.filter(historical_year=year).order_by('academic_year', 'class_name', 'last_name', 'first_name')
    students = []
    for s in students_qs[:500]:  # حد معقول للعرض
        students.append({
            'id': s.id,
            'first_name': s.first_name,
            'last_name': s.last_name,
            'academic_year': s.academic_year or '',
            'class_name': s.class_name or '',
            'class_code': s.class_code or '',
            'historical_year': s.historical_year or '',
        })

    grades_qs = HistoricalGrade.objects.filter(historical_year=year).select_related('student').order_by('student__last_name', 'subject')[:300]
    grades = []
    for g in grades_qs:
        student_name = (g.student.last_name or '') + ' ' + (g.student.first_name or '') if g.student else '—'
        grades.append({
            'student_name': student_name.strip() or '—',
            'subject': g.subject or '',
            'term': g.term or '',
            'score': g.score,
        })

    return JsonResponse({
        'status': 'success',
        'year': year,
        'students': students,
        'grades': grades,
        'students_total': HistoricalStudent.objects.filter(historical_year=year).count(),
        'grades_total': HistoricalGrade.objects.filter(historical_year=year).count(),
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
        from .models import Student, HistoricalStudent, HistoricalGrade, HistoricalImportFile, Grade, SchoolSettings
        from .expert_import_utils import find_student_advanced, parse_date, normalize_gender
        import re

        # المطابقة مع التلاميذ الموجودين في ملف النتائج للسنة الحالية (من إعدادات المؤسسة)
        from .school_year_utils import get_current_school_year
        current_school_year = get_current_school_year()

        # بناء قائمة التلاميذ المعتمدين للمطابقة (من ملف النتائج السنة الحالية - لوحة تحليل النتائج) مرة واحدة
        term_order = {'الفصل الأول': 1, 'الفصل الثاني': 2, 'الفصل الثالث': 3}
        if current_school_year:
            terms = list(Grade.objects.filter(academic_year=current_school_year).values_list('term', flat=True).distinct())
            terms = [t for t in terms if t]
            latest_term = max(terms, key=lambda t: term_order.get(t, 0)) if terms else None
            qs_ref = Grade.objects.filter(academic_year=current_school_year)
            # مرجع المطابقة = آخر فصل مستورد فقط
            if latest_term:
                qs_ref = qs_ref.filter(term=latest_term)
            student_ids_in_analytics = list(qs_ref.values_list('student_id', flat=True).distinct())
        else:
            student_ids_in_analytics = list(Grade.objects.values_list('student_id', flat=True).distinct())
        current_students_list = list(Student.objects.filter(id__in=student_ids_in_analytics))
        if not current_students_list:
            return JsonResponse({
                'status': 'error',
                'message': f"لا يوجد تلاميذ في لوحة تحليل النتائج للسنة الحالية. يرجى استيراد العلامات من لوحة تحليل النتائج (Executive) أولاً، ثم إعادة محاولة استيراد ملفات السنوات السابقة هنا."
            }, status=400)

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

                # 1. Extract Metadata (Year, Term, Level) from filename or file content
                year_pattern = r'20\d{2}[-/]\s*20\d{2}|20\d{2}[-/]20\d{2}'
                class_pattern = r'(أولى|ثانية|ثالثة|رابعة)\s*متوسط\s*\d*'
                level_pattern = r'(أولى|ثانية|ثالثة|رابعة)\s*متوسط'

                detected_year = None
                detected_class = None
                detected_level = None

                # Try filename first
                m_year = re.search(r'20\d{2}[-/]20\d{2}', filename)
                if m_year: detected_year = m_year.group(0).replace('/', '-')
                m_class = re.search(class_pattern, filename)
                if m_class: detected_class = m_class.group(0)
                m_lvl = re.search(level_pattern, filename)
                if m_lvl: detected_level = m_lvl.group(0).strip()

                # Try first 20 rows if missing
                for row in rows[:20]:
                    row_text = " ".join([str(cell) for cell in row if cell])
                    if not detected_year:
                        m = re.search(r'20\d{2}[-/]20\d{2}', row_text)
                        if m: detected_year = m.group(0).replace('/', '-')
                    if not detected_class:
                        m = re.search(class_pattern, row_text)
                        if m: detected_class = m.group(0)
                    if not detected_level:
                        m = re.search(level_pattern, row_text)
                        if m: detected_level = m.group(0).strip()

                if not detected_year:
                    errors.append(f"الملف {filename}: لم يتم العثور على السنة الدراسية (مثال: 2024-2025) في اسم الملف أو محتواه.")
                    continue

                # المستوى والقسم من الملف لا أهمية لهما — التلميذ الحالي هو الأساس؛ نستخدم مستواه وقسمه الحالي فقط

                # 2. Find Header Row and Subject Columns
                header_row_idx = -1
                subjects_map = {}

                term_map = {
                    'ف1': 'الفصل الأول', 'ف 1': 'الفصل الأول',
                    'ف2': 'الفصل الثاني', 'ف 2': 'الفصل الثاني',
                    'ف3': 'الفصل الثالث', 'ف 3': 'الفصل الثالث'
                }

                header_keywords = ('اللقب', 'الاسم', 'الرقم', 'اسم العائلة', 'العائلة', 'الاسم الشخصي', 'رقم التلميذ', 'تسلسل', 'الاسم الأول')
                for i, row in enumerate(rows[:25]):
                    row_text = " ".join([str(cell) for cell in row if cell])
                    if any(kw in row_text for kw in header_keywords):
                        header_row_idx = i
                        for col_idx, cell in enumerate(row):
                            if not cell: continue
                            val = str(cell).strip()
                            # عمود "معدل الفصل 1/2/3" يُستورد كمادة "المعدل العام" (معدل فصلي)
                            if re.search(r'معدل\s*الفصل\s*[123]', val):
                                term_num = re.search(r'[123]', val)
                                t = term_num.group(0) if term_num else '1'
                                db_term = term_map.get('ف' + t, 'الفصل الأول')
                                subjects_map[col_idx] = ('المعدل العام', db_term)
                                continue
                            if any(x in val for x in ['اللقب', 'الاسم', 'تاريخ', 'الرقم', 'رقم', 'ملاحظة', 'الجنس', 'النوع']):
                                continue
                            if val.strip() == 'المعدل' or (len(val) > 2 and 'المعدل' in val and 'معدل الفصل' not in val):
                                continue

                            m = re.search(r'(.*?)\s*(ف\s*[123])$', val)
                            if m:
                                subj = m.group(1).strip()
                                raw_term = m.group(2).strip().replace(' ', '')
                                db_term = term_map.get(raw_term, 'الفصل الأول')
                                from .import_utils import standardize_subject_name
                                subj = standardize_subject_name(subj)
                                subjects_map[col_idx] = (subj, db_term)
                            else:
                                from .import_utils import standardize_subject_name
                                subj = standardize_subject_name(val)
                                subjects_map[col_idx] = (subj, 'الفصل الأول')
                        break

                if header_row_idx == -1:
                    errors.append(f"الملف {filename}: لم يتم العثور على عناوين الجدول.")
                    continue

                if not subjects_map:
                    errors.append(f"الملف {filename}: لم يتم العثور على أعمدة المواد.")
                    continue

                # 3. Process Students and Grades
                # التطابق فقط بـ: اللقب، الاسم، تاريخ الميلاد، الجنس (لا الرقم ولا القسم)
                headers = [str(x).strip() if x else '' for x in rows[header_row_idx]]

                ln_col = -1
                fn_col = -1
                dob_col = -1
                gender_col = -1
                for idx, h in enumerate(headers):
                    if fuzzy_match_header(h, ['اللقب', 'اسم العائلة', 'العائلة']) > 80: ln_col = idx
                    if fuzzy_match_header(h, ['الاسم', 'الاسم الشخصي', 'الاسم الأول']) > 80: fn_col = idx
                    if fuzzy_match_header(h, ['تاريخ الميلاد', 'تاريخ الازدياد', 'الميلاد']) > 80: dob_col = idx
                    if fuzzy_match_header(h, ['الجنس', 'النوع']) > 80: gender_col = idx

                if ln_col == -1 or fn_col == -1:
                    errors.append(f"الملف {filename}: لم يتم التعرف على أعمدة اللقب و/أو الاسم. تأكد من وجود عناوين مثل: اللقب، الاسم.")
                    continue

                # المطابقة المتقدمة: اللقب، الاسم، تاريخ الميلاد، الجنس (تُتجاهل المستوى والأقسام)
                file_students = 0
                for row in rows[header_row_idx+1:]:
                    if not any(row): continue

                    last_name = str(row[ln_col]).strip() if ln_col >= 0 and len(row) > ln_col and row[ln_col] else ""
                    first_name = str(row[fn_col]).strip() if fn_col >= 0 and len(row) > fn_col and row[fn_col] else ""
                    file_dob = parse_date(row[dob_col]) if dob_col >= 0 and len(row) > dob_col and row[dob_col] else None
                    file_gender = normalize_gender(row[gender_col]) if gender_col >= 0 and len(row) > gender_col and row[gender_col] else None

                    if not last_name and not first_name: continue

                    # البحث بالتطابق المتقدم في تلاميذ السنة الحالية (ملف النتائج)
                    current_student = find_student_advanced(
                        current_students_list,
                        last_name=last_name,
                        first_name=first_name,
                        date_of_birth=file_dob,
                        gender=file_gender
                    )

                    if not current_student:
                        continue  # تجاهل: غير موجود في ملف النتائج السنة الحالية أو لم يُطابق

                    # التلميذ الحالي هو الأساس: نستخرج نتائجه فقط؛ المستوى والقسم = الحالي دائماً (لا نستخدم المستوى/القسم من الملف)
                    dob_val = file_dob or getattr(current_student, 'date_of_birth', None)
                    curr_level = getattr(current_student, 'academic_year', None) or '—'
                    curr_class = getattr(current_student, 'class_name', None) or '—'
                    curr_code = getattr(current_student, 'class_code', None) or '—'
                    hist_student, created = HistoricalStudent.objects.get_or_create(
                        student_id_number=current_student.student_id_number,
                        historical_year=detected_year,
                        defaults={
                            'first_name': current_student.first_name,
                            'last_name': current_student.last_name,
                            'date_of_birth': dob_val,
                            'academic_year': curr_level,
                            'class_name': curr_class,
                            'class_code': curr_code,
                        }
                    )
                    if not created and dob_val and not hist_student.date_of_birth:
                        hist_student.date_of_birth = dob_val
                        hist_student.save(update_fields=['date_of_birth'])

                    file_students += 1

                    # تسجيل النتائج في قاعدة التحليل (تراكمية: تُضاف ولا تستبدل بيانات السنة السابقة)
                    for col_idx, (subj, term) in subjects_map.items():
                        if col_idx < len(row):
                            val = row[col_idx]
                            try:
                                score = float(str(val).replace(',', '.'))
                                if 0 <= score <= 20:
                                    HistoricalGrade.objects.update_or_create(
                                        student=hist_student,
                                        subject=subj,
                                        term=term,
                                        historical_year=detected_year,
                                        defaults={'score': score}
                                    )
                                    total_grades_added += 1
                            except (ValueError, TypeError):
                                pass

                if file_students > 0:
                    total_students_processed += file_students
                    files_processed += 1
                    HistoricalImportFile.objects.create(historical_year=detected_year, filename=filename)
                else:
                    errors.append(f"الملف {filename}: لم يتم مطابقة أي صف مع التلاميذ الموجودين في لوحة تحليل النتائج. التأكيد: اللقب+الاسم+تاريخ الميلاد+الجنس يجب أن تطابق التلاميذ الذين استوردت لهم علامات السنة الحالية في لوحة التحليل.")

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
