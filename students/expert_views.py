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

    # Auto-detect latest academic year from grades if possible, so it works on older DBs
    from .models import Grade
    latest_grade = Grade.objects.order_by('-academic_year').first()
    if latest_grade and latest_grade.academic_year:
        academic_year = latest_grade.academic_year

    # Auto-detect a previous year if there is one, else just use the same or a placeholder
    prev_year = "2023-2024"
    years = Grade.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    years = [y for y in years if y]
    if len(years) > 1:
        prev_year = years[1]
    elif len(years) == 1:
        # If there's only one year of data, we can't do true cohort effect, but we can set prev_year to current_year to avoid empty querysets
        prev_year = years[0]

    context = {
        'page_title': 'تحليل خبراء التربية',
        'has_data': latest_run is not None and latest_run.status == 'completed',
        'latest_run': latest_run,
        'current_year': academic_year,
        'prev_year': prev_year
    }

    return render(request, 'students/expert_analysis.html', context)
