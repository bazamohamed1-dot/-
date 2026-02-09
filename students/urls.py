from django.urls import path, include
from . import views
from . import ui_views
from . import auth_views
from . import sync_views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', auth_views.UserManagementViewSet)
router.register(r'archive/docs', views.ArchiveDocumentViewSet, basename='archive_docs')
router.register(r'students', views.StudentViewSet)
router.register(r'pending_updates', sync_views.PendingUpdateViewSet, basename='pending_updates')
router.register(r'system_messages', sync_views.SystemMessageViewSet, basename='system_messages')

urlpatterns = [
    # Landing
    path('', ui_views.landing_view, name='canteen_landing'),
    # Auth API
    path('auth/login/', auth_views.login_view, name='auth_login'),
    path('auth/logout/', auth_views.logout_view, name='auth_logout'),
    path('auth/forgot_password/', auth_views.forgot_password, name='auth_forgot_password'),
    path('auth/verify/', auth_views.verify_session, name='auth_verify'),

    # Sync API
    path('api/sync/', sync_views.SyncViewSet.as_view({'post': 'create'}), name='sync_data'),
    path('api/offline_manifest/', views.get_offline_manifest, name='offline_manifest'),

    path('api/', include(router.urls)),

    # UI Views
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('pending_updates/', ui_views.pending_updates_view, name='pending_updates_view'),
    path('settings/', ui_views.settings_view, name='settings'),
    path('import_eleve/', ui_views.import_eleve_view, name='import_eleve_view'),
    path('api/import_json/', views.import_students_json, name='api_import_json'),
    path('ui/', ui_views.canteen_home, name='canteen_home'),
    path('list/', ui_views.student_list, name='student_list'),
    path('management/', ui_views.students_management, name='students_management'),
    path('print_cards/', ui_views.print_student_cards, name='print_student_cards'),

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

    # Library UI
    path('library/', ui_views.library_home, name='library_home'),
    path('archive/', ui_views.archive_view, name='archive_home'),
]
