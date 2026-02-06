from django.urls import path
from . import views
from . import ui_views

urlpatterns = [
    # UI Views
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('settings/', ui_views.settings_view, name='settings'),
    path('import_eleve/', ui_views.import_eleve_view, name='import_eleve_view'),
    path('ui/', ui_views.canteen_home, name='canteen_home'),
    path('list/', ui_views.student_list, name='student_list'),
    path('management/', ui_views.students_management, name='students_management'),
    path('print_cards/', ui_views.print_student_cards, name='print_student_cards'),
    path('archive/', ui_views.archive_home, name='archive_home'),

    # API Views
    path('scan_card/', views.scan_card, name='scan_card'),
    path('canteen_stats/', views.get_canteen_stats, name='canteen_stats'),
    path('manual_attendance/', views.manual_attendance, name='manual_attendance'),
    path('attendance_lists/', views.get_attendance_lists, name='attendance_lists'),
    path('export_canteen/', views.export_canteen_sheet, name='export_canteen'),

    # Library API
    path('library/scan/', views.scan_library_card, name='library_scan'),
    path('library/loan/', views.create_loan, name='library_create_loan'),
    path('library/return/', views.return_book, name='library_return_book'),
    path('library/stats/', views.library_stats, name='library_stats'),
    path('library/readers/', views.get_readers, name='library_readers'),

    # Settings API
    path('settings/data/', views.school_settings, name='school_settings'),
    path('settings/users/unlock/<int:user_id>/', views.unlock_user, name='unlock_user'),
    path('settings/users/reset/<int:user_id>/', views.reset_session, name='reset_session'),
    path('settings/users/password/<int:user_id>/', views.change_user_password, name='change_user_password'),

    # Library UI
    path('library/', ui_views.library_home, name='library_home'),
]
