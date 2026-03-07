from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ClassAlias, Student

from django.http import JsonResponse
from .models import Employee, TeacherAssignment

def resolve_class_alias(alias_str):
    """
    Looks up the alias string (e.g., '1م1') in the ClassAlias table.
    Returns (canonical_level, canonical_class) if found, else (None, None).
    """
    try:
        alias_obj = ClassAlias.objects.get(alias=alias_str.strip())
        return alias_obj.canonical_level, alias_obj.canonical_class
    except ClassAlias.DoesNotExist:
        return None, None

def class_mapping_view(request):
    """
    Interface to map imported class names (aliases) to database class names.
    """
    if not request.user.is_authenticated: return redirect('canteen_landing')

    if request.method == 'POST' and request.GET.get('action') == 'quick_save':
        emp_id = request.POST.get('employee_id')
        try:
            import json
            emp = Employee.objects.get(id=emp_id)

            assignments_data_raw = request.POST.get('assignments')
            if assignments_data_raw:
                assignments_data = json.loads(assignments_data_raw)

                TeacherAssignment.objects.filter(teacher=emp).delete()

                if assignments_data:
                    emp.subject = assignments_data[0].get('subject', '').strip()
                    emp.save()

                for assign_data in assignments_data:
                    subject = assign_data.get('subject', '').strip()
                    classes = assign_data.get('classes', [])

                    if subject:
                        TeacherAssignment.objects.create(
                            teacher=emp,
                            subject=subject,
                            classes=classes
                        )

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # 1. Get all distinct combinations of Level and Class currently in DB (for dropdown)
    db_combinations = list(
        Student.objects.exclude(academic_year__isnull=True).exclude(academic_year__exact='')
        .exclude(class_name__isnull=True).exclude(class_name__exact='')
        .values_list('academic_year', 'class_name').distinct()
    )
    # Sort them nicely: Level descending (4,3,2,1) and Class ascending (1,2,3,4)
    import re
    def sort_key(item):
        lvl, cls = item
        l_match = re.search(r'\d+', str(lvl))
        c_match = re.search(r'\d+', str(cls))
        # Negative for descending level
        l_num = -int(l_match.group()) if l_match else -999
        c_num = int(c_match.group()) if c_match else 999
        return (l_num, c_num, lvl, cls)

    db_combinations.sort(key=sort_key)

    # Format for template: "Level Class" e.g., "أولى 1"
    formatted_classes = []
    for lvl, cls in db_combinations:
        formatted_classes.append(f"{lvl} {cls}")

    # 2. Get unmapped aliases
    aliases = ClassAlias.objects.all().order_by('alias')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_alias':
            raw = request.POST.get('alias_name').strip()
            target_combined = request.POST.get('target_class') # e.g., "أولى 1"

            if raw and target_combined:
                # Split the combined string back into level and class
                # Assuming the format is exactly as we built it: "{lvl} {cls}"
                parts = target_combined.rsplit(' ', 1)

                if len(parts) == 2:
                    lvl = parts[0].strip()
                    cls = parts[1].strip()
                    ClassAlias.objects.update_or_create(
                        alias=raw,
                        defaults={'canonical_level': lvl, 'canonical_class': cls}
                    )

                    # Auto-assign teachers: Update any existing teacher assignments containing the raw alias
                    # to use the new canonical format
                    updated_assignments_count = 0
                    for assignment in TeacherAssignment.objects.all():
                        if raw in assignment.classes:
                            # Replace the alias with the canonical string and ensure uniqueness
                            new_classes = [target_combined if c == raw else c for c in assignment.classes]
                            assignment.classes = list(set(new_classes))
                            assignment.save()
                            updated_assignments_count += 1

                    if updated_assignments_count > 0:
                        messages.success(request, f"تم ربط '{raw}' بـ '{target_combined}' وتم تحديث الإسناد لـ {updated_assignments_count} أستاذ آلياً.")
                    else:
                        messages.success(request, f"تم ربط '{raw}' بـ '{target_combined}' بنجاح.")
                else:
                    messages.error(request, "تنسيق القسم غير صالح.")

        elif action == 'delete_alias':
            pk = request.POST.get('pk')
            ClassAlias.objects.filter(pk=pk).delete()
            messages.success(request, "تم حذف الربط")

        return redirect('class_mapping_view')

    context = {
        'db_classes': formatted_classes,
        'aliases': aliases
    }
    return render(request, 'students/class_mapping.html', context)
