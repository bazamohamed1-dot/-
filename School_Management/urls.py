from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet
from students import ui_views

router = DefaultRouter()
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('', ui_views.dashboard, name='home'), # Redirect root to dashboard
    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('canteen/', include('students.urls')), # This now includes dashboard paths too based on previous step
]
