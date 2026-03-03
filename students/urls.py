from django.urls import path, include
from . import views
from . import ui_views
from . import auth_views
from . import qr_views
from . import ai_views
from . import reminder_views
from . import mapping_views # New
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', auth_views.UserManagementViewSet)
router.register(r'roles', auth_views.UserRoleViewSet)
router.register(r'archive/docs', views.ArchiveDocumentViewSet, basename='archive_docs')
router.register(r'students', views.StudentViewSet)
router.register(r'system_messages', views.SystemMessageViewSet, basename='system_messages')
router.register(r'pending_updates', views.PendingUpdateViewSet, basename='pending_updates')

# AI & Tasks
router.register(r'tasks', ai_views.TaskViewSet, basename='tasks')
router.register(r'school_memory', ai_views.SchoolMemoryViewSet, basename='school_memory')

urlpatterns = [
    # Landing
    path('', ui_views.landing_view, name='canteen_landing'),
    # Auth API
    path('auth/login/', auth_views.login_view, name='auth_login'),
    path('auth/logout/', auth_views.logout_view, name='auth_logout'),
    path('auth/forgot_password/', auth_views.forgot_password, name='auth_forgot_password'),
    path('auth/password/reset/request/', auth_views.RequestPasswordResetView.as_view(), name='password_reset_request'),
    path('auth/password/reset/confirm/', auth_views.ConfirmPasswordResetView.as_view(), name='password_reset_confirm'),
    path('auth/password/change/', auth_views.ForceChangePasswordView.as_view(), name='password_change'),
    path('auth/verify/', auth_views.verify_session, name='auth_verify'),
    path('auth/2fa/setup/', auth_views.setup_2fa, name='auth_2fa_setup'),
    path('auth/2fa/confirm/', auth_views.confirm_2fa, name='auth_2fa_confirm'),
    path('auth/2fa/disable/', auth_views.disable_2fa, name='auth_2fa_disable'),
    path('auth/2fa/login/', auth_views.verify_2fa_login, name='auth_2fa_login'),

    # QR Generation
    path('api/generate_qr/', qr_views.generate_user_qr, name='generate_user_qr'),

    path('api/students/filters/', views.student_filters, name='student_filters'),
    path('api/', include(router.urls)),

    # UI Views
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('pending_updates/', ui_views.pending_updates_view, name='pending_updates_view'),
    path('settings/', ui_views.settings_view, name='settings'),
    path('import_eleve/', ui_views.import_eleve_view, name='import_eleve_view'),
    path('import_eleve/confirm/', ui_views.import_eleve_confirm, name='import_eleve_confirm'),
    path('api/import_json/', views.import_students_json, name='api_import_json'),
    path('api/import/update/', views.upload_update_file, name='api_import_update'),
    path('sync/photos/', ui_views.sync_photos_view, name='sync_photos_view'),
    path('ui/', ui_views.canteen_home, name='canteen_home'),
    path('list/', ui_views.student_list, name='student_list'),
    path('management/', ui_views.students_management, name='students_management'),
    path('print_cards/', ui_views.print_student_cards, name='print_student_cards'),

    # API Views
    path('scan_card/', views.scan_card, name='scan_card'),
    path('canteen_stats/', views.get_canteen_stats, name='canteen_stats'),
    path('manual_attendance/', views.manual_attendance, name='manual_attendance'),
    path('delete_attendance/', views.delete_attendance, name='delete_attendance'),
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

    # Library UI
    path('library/', ui_views.library_home, name='library_home'),
    path('archive/', ui_views.archive_view, name='archive_home'),

    # New Interfaces
    path('hr/', ui_views.hr_home, name='hr_home'),
    path('hr/assignment_match/', ui_views.assignment_matching_view, name='assignment_matching_view'),
    path('hr/mapping/', mapping_views.class_mapping_view, name='class_mapping_view'),
    path('hr/<int:pk>/delete/', ui_views.hr_delete, name='hr_delete'),
    path('parents/', ui_views.parents_home, name='parents_home'),
    path('guidance/', ui_views.guidance_home, name='guidance_home'),

    # AI & Task UI
    path('tasks/', ui_views.tasks_view, name='tasks_view'),
    path('ai/control/', ui_views.ai_control_panel, name='ai_control_panel'),
    path('ai/chat/', ui_views.ai_chat_view, name='ai_chat_view'),
    path('ai/manual/', ui_views.ai_manual_view, name='ai_manual_view'),

    # Reminders
    path('api/reminders/', reminder_views.check_reminders, name='check_reminders'),
    path('analytics/', ui_views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics_test/', ui_views.analytics_dashboard, name='analytics_test'),
    path('analytics/upload_grades_ajax/', ui_views.upload_grades_ajax, name='upload_grades_ajax'),
    path('analytics/advanced/', ui_views.advanced_analytics_view, name='advanced_analytics_view'),
]
