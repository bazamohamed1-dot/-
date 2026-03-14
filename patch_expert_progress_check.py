with open('students/templates/students/expert_analysis.html', 'r') as f:
    content = f.read()
if "startExpertProgress" not in content:
    print("FAILED TO PATCH PROGRESS")
