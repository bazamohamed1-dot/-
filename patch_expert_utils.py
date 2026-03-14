with open('students/expert_utils.py', 'r') as f:
    content = f.read()

content = content.replace("from .models import Grade, Student, ExpertAnalysisRun, StudentExpertData, CohortExpertData",
                          "from .models import Grade, Student, ExpertAnalysisRun, StudentExpertData, CohortExpertData, HistoricalGrade")

content = content.replace("prev_grades = Grade.objects.filter(academic_year=prev_academic_year).select_related('student')",
                          "prev_grades = HistoricalGrade.objects.filter(historical_year=prev_academic_year).select_related('student')")

content = content.replace("prev_data = list(prev_grades.values('student__id', 'student__student_id_number', 'student__academic_year', 'subject', 'term', 'score'))",
                          "prev_data = list(prev_grades.values('student__id', 'student__student_id_number', 'student__academic_year', 'subject', 'term', 'score'))")

with open('students/expert_utils.py', 'w') as f:
    f.write(content)
