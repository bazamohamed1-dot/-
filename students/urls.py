from django.urls import path
from . import views
from . import ui_views

urlpatterns = [
    # UI Views
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('settings/', ui_views.settings_view, name='settings'),
    path('import_eleve/', ui_views.import_eleve_view, name='import_eleve_view'),
    path('ui/', ui_views.canteen_home, name='canteen_home'), # Removed 'canteen/' prefix here
    path('list/', ui_views.student_list, name='student_list'), # Renamed for clarity

    # API Views
    path('scan_card/', views.scan_card, name='scan_card'),
    path('canteen_stats/', views.get_canteen_stats, name='canteen_stats'),
    path('manual_attendance/', views.manual_attendance, name='manual_attendance'),
    path('attendance_lists/', views.get_attendance_lists, name='attendance_lists'),
    path('export_canteen/', views.export_canteen_sheet, name='export_canteen'),
]
