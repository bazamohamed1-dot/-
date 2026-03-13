import re

with open('students/ui_views.py', 'r') as f:
    content = f.read()

# Replace hr_delete view
old_view = """def hr_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    get_object_or_404(Employee, pk=pk).delete()
    messages.success(request, "تم الحذف")
    return redirect('hr_home')"""

new_view = """def hr_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('canteen_landing')
    if hasattr(request.user, 'profile') and not request.user.profile.has_perm('access_hr'):
        return redirect('dashboard')

    try:
        emp = Employee.objects.get(pk=pk)
        emp.delete()
        messages.success(request, "تم الحذف")
    except Employee.DoesNotExist:
        messages.warning(request, "هذا الموظف غير موجود أو تم حذفه مسبقاً.")
    return redirect('hr_home')"""

if old_view in content:
    content = content.replace(old_view, new_view)
    with open('students/ui_views.py', 'w') as f:
        f.write(content)
    print("Patched hr_delete")
else:
    print("Could not find exact old_view text.")
