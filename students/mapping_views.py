from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ClassAlias, Student

def class_mapping_view(request):
    """
    Interface to map imported class names (aliases) to database class names.
    """
    if not request.user.is_authenticated: return redirect('canteen_landing')

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
