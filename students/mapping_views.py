from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ClassAlias, Student

from django.http import JsonResponse
from .models import Employee, TeacherAssignment

def class_mapping_view(request):
    """
    Interface to map imported class names (aliases) to database class names.
    """
    if not request.user.is_authenticated: return redirect('canteen_landing')

    if request.method == 'POST' and request.GET.get('action') == 'quick_save':
        emp_id = request.POST.get('employee_id')
        subject = request.POST.get('subject', '').strip()
        classes = request.POST.getlist('classes')
        try:
            emp = Employee.objects.get(id=emp_id)
            emp.subject = subject
            emp.save()

            assign, created = TeacherAssignment.objects.get_or_create(teacher=emp)
            assign.subject = subject
            assign.classes = classes
            assign.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # 1. Get all distinct classes currently in DB (for dropdown)
    db_classes = list(Student.objects.values_list('class_name', flat=True).distinct())
    db_classes.sort()

    # 2. Get unmapped aliases (Optional: Store pending mappings in session or DB)
    # For this flow, we will just allow user to create aliases manually or from recent import attempts.
    # But since we don't persist "failed import rows", we just list existing aliases for editing.

    aliases = ClassAlias.objects.all().order_by('alias')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_alias':
            raw = request.POST.get('alias_name').strip()
            target = request.POST.get('target_class')

            if raw and target:
                ClassAlias.objects.update_or_create(
                    alias=raw,
                    defaults={'canonical_class': target}
                )
                messages.success(request, f"تم ربط '{raw}' بـ '{target}'")

        elif action == 'delete_alias':
            pk = request.POST.get('pk')
            ClassAlias.objects.filter(pk=pk).delete()
            messages.success(request, "تم حذف الربط")

        return redirect('class_mapping_view')

    context = {
        'db_classes': db_classes,
        'aliases': aliases
    }
    return render(request, 'students/class_mapping.html', context)
