from django.contrib import admin
from django.urls import path, include # اضفنا include
from rest_framework.routers import DefaultRouter
from students.views import StudentViewSet, index # استوردنا الـ ViewSet و index

# إنشاء راوتر تلقائي لإنشاء مسارات API لـ CRUD والبحث
router = DefaultRouter()
router.register(r'students', StudentViewSet) # هذا السطر يربط /students/ بكل الأوامر

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    # إضافة مسارات الـ API الخاصة بنا
    path('api/', include(router.urls)),
]
