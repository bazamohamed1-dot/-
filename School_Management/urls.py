from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet
from students import ui_views

router = DefaultRouter()
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('', ui_views.login_view, name='root'),
    path('login/', ui_views.login_view, name='login'),
    path('logout/', ui_views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('', include('students.urls')),
]
