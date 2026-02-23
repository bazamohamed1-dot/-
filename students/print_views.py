from django.shortcuts import render
from django.db.models import Q
from .models import Student
from .utils import normalize_arabic

def print_student_cards(request):
    """
    Handle POST request for printing cards.
    Accepts:
      - student_ids (list of IDs)
      - select_all_matching (bool) + filter params
    """
    if request.method != 'POST':
         # Redirect or show error, but better to just render empty or redirect to management
         return render(request, 'students/management.html', {'error': 'Method not allowed'})

    # Check for Select All Matching
    select_all = request.POST.get('select_all_matching') == 'true'

    if select_all:
        # Re-construct queryset based on filters
        qs = Student.objects.all().order_by('last_name', 'first_name')

        level = request.POST.get('filter_level')
        cls = request.POST.get('filter_class')
        search = request.POST.get('filter_search')

        if level: qs = qs.filter(academic_year=level)
        if cls: qs = qs.filter(class_name=cls)
        if search:
            # Re-apply search logic (Duplicate code - ideally refactor to util)
            norm_search = normalize_arabic(search)
            q_obj = Q(student_id_number__icontains=search) | \
                    Q(first_name__icontains=search) | \
                    Q(last_name__icontains=search)
            if norm_search != search:
                q_obj |= Q(first_name__icontains=norm_search) | \
                         Q(last_name__icontains=norm_search)
            if 'ه' in search:
                 alt = search.replace('ه', 'ة')
                 q_obj |= Q(first_name__icontains=alt) | Q(last_name__icontains=alt)
            if 'ة' in search:
                 alt = search.replace('ة', 'ه')
                 q_obj |= Q(first_name__icontains=alt) | Q(last_name__icontains=alt)
            qs = qs.filter(q_obj)

        students = qs
    else:
        # Standard ID list
        ids = request.POST.getlist('student_ids')
        if not ids:
             return render(request, 'students/management.html', {'error': 'No students selected'})
        students = Student.objects.filter(id__in=ids)

    # Render Template
    # We assume 'students/cards_print.html' exists or needs to be created.
    # The current system likely uses `ui_views.print_student_cards`.
    # Let's check `ui_views.py` content first.

    return render(request, 'students/cards_print.html', {'students': students})
