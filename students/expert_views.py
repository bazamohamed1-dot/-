from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import ExpertAnalysisRun, StudentExpertData, CohortExpertData, SchoolSettings
import json

@login_required
def expert_analysis_view(request):
    """
    Renders the Expert Analysis Dashboard (الخبراء).
    Requires 'director' or equivalent permission.
    """
    if not request.user.profile.has_perm('access_analytics'):
        return render(request, 'students/unauthorized.html')

    # Fetch latest run data
    latest_run = ExpertAnalysisRun.objects.order_by('-run_date').first()

    settings = SchoolSettings.objects.first()
    academic_year = settings.academic_year if settings else "2024-2025"

    context = {
        'page_title': 'تحليل خبراء التربية',
        'has_data': latest_run is not None and latest_run.status == 'completed',
        'latest_run': latest_run,
        'current_year': academic_year
    }

    return render(request, 'students/expert_analysis.html', context)
