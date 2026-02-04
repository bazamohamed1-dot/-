from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('ui/', TemplateView.as_view(template_name='canteen_interface.html'), name='canteen_ui'),
    path('scan_card/', views.scan_card, name='scan_card'),
    path('canteen_stats/', views.get_canteen_stats, name='canteen_stats'),
    path('manual_attendance/', views.manual_attendance, name='manual_attendance'),
    path('attendance_lists/', views.get_attendance_lists, name='attendance_lists'),
    path('export_canteen/', views.export_canteen_sheet, name='export_canteen'),
]
