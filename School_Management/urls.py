from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet
from students import ui_views
from students import auth_views
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('', ui_views.landing_view, name='landing'),
    path('dashboard/', ui_views.dashboard, name='dashboard'),
    path('auth/login/', auth_views.login_view, name='login'),

    # Service Worker (Renamed to service-worker.js to bypass stuck cache)
    path('service-worker.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw_new'),
    # Keep old sw.js URL returning nothing (or 404/empty) to help browsers unregister it naturally
    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw_old'),

    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('canteen/', include('students.urls')),

    # Explicitly serve media files using 'serve' view even if DEBUG=False
    # This is crucial for local deployments (Waitress/Gunicorn) where Nginx is not present
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]
