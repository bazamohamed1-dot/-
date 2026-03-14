import re

filepath = "./students/ui_views.py"
with open(filepath, "r") as f:
    content = f.read()

# Make hr_delete support JSON response if requested via AJAX
replacement = """def hr_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('accept', '').startswith('application/json')

    try:
        emp = Employee.objects.get(pk=pk)
        emp.delete()
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم الحذف'})
        messages.success(request, "تم الحذف")
    except Employee.DoesNotExist:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'هذا الموظف غير موجود أو تم حذفه مسبقاً.'})
        messages.warning(request, "هذا الموظف غير موجود أو تم حذفه مسبقاً.")

    return redirect('hr_home')"""

# We need to replace the hr_delete block safely
# Regex to find the whole hr_delete block until the next def
pattern = re.compile(r'def hr_delete\(request, pk\):.*?return redirect\(\'hr_home\'\)', re.DOTALL)
content = pattern.sub(replacement, content)

with open(filepath, "w") as f:
    f.write(content)

print("Patched hr_delete in ui_views.py")
