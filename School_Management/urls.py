from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet
from students import ui_views
from students import auth_views

router = DefaultRouter()
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('', ui_views.landing_view, name='landing'),
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('auth/login/', auth_views.login_view, name='login'),

    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('canteen/', include('students.urls')),
]
