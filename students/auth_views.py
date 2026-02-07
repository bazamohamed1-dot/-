from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import EmployeeProfile, UserActivityLog, SchoolSettings
import secrets

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    username = request.data.get('username')
    try:
        settings_obj = SchoolSettings.objects.first()
        if not settings_obj or not settings_obj.admin_email:
             return Response({'error': 'لم يتم ضبط بريد المدير في الإعدادات.'}, status=400)

        # We don't verify if user exists to prevent enumeration, or we do?
        # User asked to restore. Let's verify.
        if not User.objects.filter(username=username).exists():
             return Response({'error': 'اسم المستخدم غير موجود'}, status=404)

        # In a real app, send email. Here, we simulate.
        print(f"--- SIMULATED EMAIL TO {settings_obj.admin_email} ---")
        print(f"Subject: استعادة كلمة المرور للمستخدم {username}")
        print(f"Body: يرجى التواصل مع المستخدم لإعادة تعيين كلمة المرور.")
        print("-------------------------------------------------------")

        return Response({'message': f'تم إرسال طلب الاستعادة إلى المدير ({settings_obj.admin_email})'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'}, status=status.HTTP_400_BAD_REQUEST)

    if not hasattr(user, 'profile'):
        # Auto-create profile for superuser or legacy users if missing, defaulting to director for safety if superuser
        role = 'director' if user.is_superuser else 'secretariat'
        EmployeeProfile.objects.create(user=user, role=role)

    profile = user.profile

    if profile.is_locked:
        return Response({'error': 'الحساب مقفل. يرجى الاتصال بالمدير.', 'code': 'LOCKED'}, status=status.HTTP_403_FORBIDDEN)

    user_auth = authenticate(username=username, password=password)

    if user_auth is not None:
        # Success
        profile.failed_login_attempts = 0

        # Generate Session Token
        token = secrets.token_hex(32)
        profile.current_session_token = token
        profile.save()

        login(request, user)

        # Log Activity
        UserActivityLog.objects.create(user=user, action='login')

        return Response({
            'message': 'تم تسجيل الدخول بنجاح',
            'token': token,
            'role': profile.role,
            'username': user.username
        })
    else:
        # Fail
        profile.failed_login_attempts += 1
        if profile.failed_login_attempts >= 3:
            profile.is_locked = True
            profile.save()
            return Response({'error': 'تم قفل الحساب بسبب تكرار المحاولات الخاطئة. اتصل بالمدير.', 'code': 'LOCKED'}, status=status.HTTP_403_FORBIDDEN)

        profile.save()
        remaining = 3 - profile.failed_login_attempts
        return Response({'error': f'معلومات غير صحيحة. بقي لديك {remaining} محاولات.', 'code': 'INVALID_CREDS'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def verify_session(request):
    token = request.data.get('token')
    if not request.user.is_authenticated:
        return Response({'valid': False, 'reason': 'NOT_LOGGED_IN'}, status=401)

    try:
        profile = request.user.profile
        # If token matches DB, session is valid.
        if profile.current_session_token == token:
            return Response({'valid': True, 'role': profile.role})
        else:
            return Response({'valid': False, 'reason': 'SESSION_MISMATCH'}, status=401)
    except:
        return Response({'valid': False}, status=401)

@api_view(['POST'])
def logout_view(request):
    if request.user.is_authenticated:
        try:
            p = request.user.profile
            p.current_session_token = None
            p.save()
            UserActivityLog.objects.create(user=request.user, action='logout')
        except:
            pass
        logout(request)
    return Response({'message': 'Logged out'})

class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def check_permission(self, request, perm):
        if not hasattr(request.user, 'profile'): return False
        return request.user.profile.has_perm(perm)

    def list(self, request):
        if not self.check_permission(request, 'manage_users'):
            return Response({'error': 'Unauthorized'}, status=403)

        users = User.objects.select_related('profile').all().distinct()
        data = []
        seen = set()
        for u in users:
            if u.id in seen: continue
            seen.add(u.id)
            try:
                prof = u.profile
                data.append({
                    'id': u.id,
                    'username': u.username,
                    'role': prof.role,
                    'role_display': prof.get_role_display(),
                    'is_locked': prof.is_locked,
                    'failed_attempts': prof.failed_login_attempts,
                    'permissions': prof.permissions
                })
            except:
                pass
        return Response(data)

    def create(self, request):
        if not self.check_permission(request, 'manage_users'):
            return Response({'error': 'Unauthorized'}, status=403)

        username = request.data.get('username')
        password = request.data.get('password')
        role = request.data.get('role')
        permissions = request.data.get('permissions', [])

        if role == 'director':
            if EmployeeProfile.objects.filter(role='director').exists():
                return Response({'error': 'لا يمكن إنشاء أكثر من حساب مدير واحد'}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'اسم المستخدم موجود بالفعل'}, status=400)

        user = User.objects.create_user(username=username, password=password)
        EmployeeProfile.objects.create(user=user, role=role, permissions=permissions)
        return Response({'message': 'User created'})

    def destroy(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        user = self.get_object()
        if user == request.user:
             return Response({'error': 'لا يمكنك حذف حسابك الخاص'}, status=400)

        if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'director'):
             return Response({'error': 'لا يمكن حذف المدير'}, status=400)

        user.delete()
        return Response({'message': 'User deleted'})

    @action(detail=True, methods=['post'])
    def update_creds(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        user = self.get_object()
        new_pass = request.data.get('password')
        new_username = request.data.get('username')
        permissions = request.data.get('permissions')
        role = request.data.get('role')

        if new_username:
            user.username = new_username
        if new_pass:
            user.set_password(new_pass)
        user.save()

        if hasattr(user, 'profile'):
            if permissions is not None:
                user.profile.permissions = permissions
            if role:
                user.profile.role = role
            user.profile.save()

        return Response({'message': 'Profile updated'})

    @action(detail=True, methods=['post'])
    def unlock_account(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        user = self.get_object()
        profile = user.profile
        profile.is_locked = False
        profile.failed_login_attempts = 0
        profile.save()
        return Response({'message': 'Account unlocked'})

    @action(detail=True, methods=['post'])
    def reset_session(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        user = self.get_object()
        profile = user.profile
        profile.current_session_token = None
        profile.save()
        return Response({'message': 'Session reset'})

    @action(detail=False, methods=['get'])
    def logs(self, request):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        logs = UserActivityLog.objects.select_related('user').all()[:200]
        data = []
        for log in logs:
             data.append({
                 'username': log.user.username,
                 'action': log.action,
                 'timestamp': log.timestamp
             })
        return Response(data)

    @action(detail=False, methods=['post'])
    def clear_logs(self, request):
        if not self.check_permission(request, 'manage_users'):
             return Response({'error': 'Unauthorized'}, status=403)

        UserActivityLog.objects.all().delete()
        return Response({'message': 'Logs cleared'})
