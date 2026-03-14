with open('students/expert_api_views.py', 'r') as f:
    content = f.read()

# Update api_expert_available_years to count HistoricalGrade instead of Grade
content = content.replace("from .models import Grade", "from .models import HistoricalGrade")
content = content.replace("years = Grade.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')",
                          "years = HistoricalGrade.objects.values_list('historical_year', flat=True).distinct().order_by('-historical_year')")

with open('students/expert_api_views.py', 'w') as f:
    f.write(content)
