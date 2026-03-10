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

            # Run in a background thread
            thread = threading.Thread(target=run_expert_engine, args=(current_year, current_term, prev_year))
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
