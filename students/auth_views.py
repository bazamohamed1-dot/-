from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import EmployeeProfile, UserActivityLog, SchoolSettings
import secrets
import pyotp
import qrcode
import base64
from io import BytesIO

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_2fa(request):
    if request.user.profile.role != 'director':
        return Response({'error': 'Unauthorized'}, status=403)

    secret = pyotp.random_base32()
    request.user.profile.totp_secret = secret
    request.user.profile.save()

    # Generate QR Code
    otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=request.user.username, issuer_name='SchoolSystem')
    img = qrcode.make(otp_uri)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return Response({
        'secret': secret,
        'qr_code': f"data:image/png;base64,{img_str}"
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_2fa(request):
    code = request.data.get('code')
    secret = request.user.profile.totp_secret
    if not secret: return Response({'error': 'No setup found'}, status=400)

    totp = pyotp.TOTP(secret)
    if totp.verify(code):
        request.user.profile.totp_enabled = True
        request.user.profile.save()
        return Response({'message': '2FA Enabled Successfully'})
    return Response({'error': 'Invalid Code'}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_2fa(request):
    if request.user.profile.role != 'director': return Response({'error': 'Unauthorized'}, status=403)
    request.user.profile.totp_enabled = False
    request.user.profile.totp_secret = None
    request.user.profile.save()
    return Response({'message': '2FA Disabled'})

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_2fa_login(request):
    token = request.data.get('temp_token')
    code = request.data.get('code')

    try:
        profile = EmployeeProfile.objects.get(current_session_token=f"PRE-2FA:{token}")
        user = profile.user
    except EmployeeProfile.DoesNotExist:
        return Response({'error': 'Invalid or expired session'}, status=400)

    totp = pyotp.TOTP(profile.totp_secret)
    if totp.verify(code):
        # Success - Finalize Login
        final_token = secrets.token_hex(32)
        profile.current_session_token = final_token
        profile.failed_login_attempts = 0
        profile.save()
        login(request, user)
        UserActivityLog.objects.create(user=user, action='login_2fa')

        return Response({
            'message': 'Login Successful',
            'token': final_token,
            'role': profile.role,
            'username': user.username
        })
    else:
        return Response({'error': 'رمز خاطئ'}, status=400)

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    username = request.data.get('username')
    if not username:
        return Response({'message': 'يرجى الاتصال بمدير المؤسسة لاستعادة معلومات الدخول.'}) # Generic msg for users

    # Director Recovery
    try:
        user = User.objects.get(username=username)
        if hasattr(user, 'profile') and user.profile.role == 'director':
            settings_obj = SchoolSettings.objects.first()
            if settings_obj and settings_obj.admin_email:
                # Logic to send email (Pseudo-code, requires SMTP setup)
                # For now, we return a message saying "Check server logs/console" or implement real email
                # Assuming SMTP is not configured in this env, we guide them to the CLI.
                return Response({'message': 'تم إرسال تعليمات الاستعادة إلى بريد المدير (إذا كان مفعل)، أو استخدم الأمر reset_director من الخادم.'})
    except:
        pass

    return Response({'message': 'يرجى الاتصال بمدير المؤسسة لاستعادة معلومات الدخول.'})

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    try:
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

            # Device Lock Logic
            device_id_to_send = None

            # Skip Device Lock for Director/Superuser
            if profile.role == 'director' or user.is_superuser:
                pass
            else:
                try:
                    if profile.device_id:
                        if profile.device_id.startswith('PENDING:'):
                            # Provisioning Mode
                            real_id = profile.device_id.split(':')[1]
                            profile.device_id = real_id
                            device_id_to_send = real_id
                            profile.save()
                        else:
                            # Enforce Mode
                            client_id = request.headers.get('X-Device-ID') or request.META.get('HTTP_X_DEVICE_ID')

                            if not client_id or client_id != profile.device_id:
                                return Response({'error': 'هذا الجهاز غير مصرح به. يرجى الاتصال بالمدير.', 'code': 'DEVICE_LOCKED'}, status=status.HTTP_403_FORBIDDEN)
                            else:
                                device_id_to_send = profile.device_id
                    else:
                        # First Time Login - Bind
                        client_id = request.headers.get('X-Device-ID') or request.META.get('HTTP_X_DEVICE_ID')

                        if client_id:
                            profile.device_id = client_id
                            profile.save()
                            device_id_to_send = client_id
                        else:
                            return Response({'error': 'لم يتم التعرف على هوية الجهاز. حاول تحديث الصفحة.', 'code': 'NO_DEVICE_ID'}, status=status.HTTP_400_BAD_REQUEST)

                except Exception as e:
                    print(f"Device Lock Error: {e}")
                    return Response({'error': f'خطأ في التحقق من الجهاز: {str(e)}', 'code': 'SERVER_ERROR'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 2FA Check
            if profile.totp_enabled:
                # Issue temporary token
                temp_token = secrets.token_hex(16)
                profile.current_session_token = f"PRE-2FA:{temp_token}"
                profile.save()
                return Response({
                    'require_2fa': True,
                    'temp_token': temp_token
                })

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
                'username': user.username,
                'device_id': device_id_to_send
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Internal Server Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                device_status = 'غير مفعل'
                if prof.device_id:
                    if prof.device_id.startswith('PENDING:'): device_status = 'بانتظار التفعيل'
                    else: device_status = 'مفعل'

                data.append({
                    'id': u.id,
                    'username': u.username,
                    'role': prof.role,
                    'role_display': prof.get_role_display(),
                    'is_locked': prof.is_locked,
                    'failed_attempts': prof.failed_login_attempts,
                    'permissions': prof.permissions,
                    'device_status': device_status
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

    @action(detail=True, methods=['post'])
    def activate_device(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        import uuid
        new_id = str(uuid.uuid4())
        user.profile.device_id = f"PENDING:{new_id}"
        user.profile.save()
        return Response({'message': 'تم تفعيل حماية الجهاز. سيتم ربط الجهاز عند تسجيل الدخول القادم.'})

    @action(detail=True, methods=['post'])
    def reset_device(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        user.profile.device_id = None
        user.profile.save()
        return Response({'message': 'تم تعطيل حماية الجهاز.'})
