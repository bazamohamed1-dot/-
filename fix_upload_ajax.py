import re

file_path = './students/ui_views.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """def upload_grades_ajax(request):
    \"\"\"Handles bulk uploading of multiple grade files with AJAX progress\"\"\"
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        term = request.POST.get('term')
        import_mode = request.POST.get('import_mode', 'local')

        import tempfile
        import os
        from .grade_importer import process_grades_file, process_grades_file_ai

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.name}") as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

            if import_mode == 'ai':
                count, msg = process_grades_file_ai(temp_path, term)
            else:
                count, msg = process_grades_file(temp_path, term)

            success = count > 0
            return JsonResponse({'success': success, 'message': msg, 'count': count})"""

content = re.sub(r"def upload_grades_ajax\(request\):.*?return JsonResponse\(\{.*?\}\)", replacement, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated upload_grades_ajax to support import_mode")
