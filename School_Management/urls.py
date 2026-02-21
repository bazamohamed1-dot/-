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

    # Service Worker (Renamed to service-worker.js to bypass stuck cache)
    path('service-worker.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw_new'),
    # Keep old sw.js URL returning nothing (or 404/empty) to help browsers unregister it naturally
    path('sw.js', TemplateView.as_view(template_name="sw.js", content_type='application/javascript'), name='sw_old'),

    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('canteen/', include('students.urls')),
]

# Serve static and media files during development and local production (if DEBUG=False with specific setup or True)
# For simple local setup, serving via Django is easiest, even with DEBUG=False if using 'insecure' runserver or WhiteNoise for static.
# Media files need manual serving if DEBUG=False unless using a specific server config.
# We will use this pattern which works for both runserver modes usually.
# Always serve media/static files locally for this specific deployment style (Waitress)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
