from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
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

    # Service Worker
    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw'),

    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('canteen/', include('students.urls')),
]

# Serve static and media files during development and local production (if DEBUG=False with specific setup or True)
# For simple local setup, serving via Django is easiest, even with DEBUG=False if using 'insecure' runserver or WhiteNoise for static.
# Media files need manual serving if DEBUG=False unless using a specific server config.
# We will use this pattern which works for both runserver modes usually.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Force serve media in local production mode without Nginx/Apache
    import re
    from django.views.static import serve
    from django.urls import re_path

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]
