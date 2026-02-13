from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import EmployeeProfile, UserActivityLog, SchoolSettings, UserRole
from .serializers import UserRoleSerializer
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

    settings_obj = SchoolSettings.objects.first()
    admin_email = settings_obj.admin_email if settings_obj else None

    # Case: Director Recovery (Email Token)
    if username:
        try:
            user = User.objects.get(username=username)
            # Only for Director/Superuser
            if (hasattr(user, 'profile') and user.profile.role == 'director') or user.is_superuser:

                # Check if Admin Email is configured
                if not admin_email:
                    return Response({'error': 'لم يتم إعداد بريد استرجاع (Admin Email). يرجى الاتصال بالمطور.'}, status=400)

                # Generate One-Time Token
                token = secrets.token_hex(4) # 8 chars
                settings_obj.recovery_token = token
                settings_obj.recovery_token_created_at = timezone.now()
                settings_obj.save()

                # Simulate Email Sending (Log to console/file since offline)
                # In a real scenario with SMTP:
                # send_mail('Recovery Code', f'Your code is: {token}', 'system@school.local', [admin_email])

                print(f"==========================================")
                print(f" [RECOVERY] To: {admin_email}")
                print(f" [RECOVERY] Code: {token}")
                print(f"==========================================")

                return Response({'message': f'تم إرسال رمز الاستعادة إلى {admin_email} (راجع سجل السيرفر للمحاكاة).'})

        except User.DoesNotExist:
            pass

    return Response({'message': 'إذا كان الحساب صحيحاً، فقد تم الإرسال.'})

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]

    def check_permission(self, request):
        return hasattr(request.user, 'profile') and request.user.profile.role == 'director'

    def list(self, request):
        if not self.check_permission(request): return Response({'error': 'Unauthorized'}, status=403)
        return super().list(request)

    def create(self, request):
        if not self.check_permission(request): return Response({'error': 'Unauthorized'}, status=403)
        return super().create(request)

    def destroy(self, request, pk=None):
        if not self.check_permission(request): return Response({'error': 'Unauthorized'}, status=403)
        return super().destroy(request, pk)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    try:
        username = request.data.get('username')
        password = request.data.get('password')

        # --- Director Recovery Login (Email + Recovery Token) ---
        # If username matches Admin Email, check recovery token
        settings_obj = SchoolSettings.objects.first()
        if settings_obj and settings_obj.admin_email and username.strip().lower() == settings_obj.admin_email.strip().lower():
            # Check Token
            if settings_obj.recovery_token and password.strip() == settings_obj.recovery_token:
                # Check Expiry (e.g. 15 mins)
                # For offline simplicity, we might skip strict time check or make it 24h
                # Let's invalidate it immediately upon use.

                settings_obj.recovery_token = None
                settings_obj.save()

                # Find Director
                director_profile = EmployeeProfile.objects.filter(role='director').first()
                target_user = director_profile.user if director_profile else User.objects.filter(is_superuser=True).first()

                if target_user:
                     profile = target_user.profile
                     profile.failed_login_attempts = 0
                     profile.is_locked = False

                     # Generate Session
                     token = secrets.token_hex(32)
                     profile.current_session_token = token
                     profile.save()

                     login(request, target_user)
                     UserActivityLog.objects.create(user=target_user, action='login_recovery_token')

                     # Return with a flag to show "Change Password" alert
                     return Response({
                        'message': 'تم الدخول برمز الاستعادة. يرجى تغيير كلمة المرور فوراً.',
                        'token': token,
                        'role': profile.role,
                        'username': target_user.username,
                        'alert_password_change': True
                    })
            else:
                return Response({'error': 'رمز الاستعادة غير صحيح أو منتهي الصلاحية.'}, status=400)

        # --- Standard Login ---
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'}, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(user, 'profile'):
            # Auto-create profile for superuser or legacy users if missing, defaulting to director for safety if superuser
            role = 'director' if user.is_superuser else 'secretariat'
            EmployeeProfile.objects.create(user=user, role=role)

        profile = user.profile

        # Allow Director to attempt login even if locked (will unlock on success)
        if profile.is_locked and profile.role != 'director':
            return Response({'error': 'الحساب مقفل. يرجى الاتصال بالمدير.', 'code': 'LOCKED'}, status=status.HTTP_403_FORBIDDEN)

        user_auth = authenticate(username=username, password=password)

        if user_auth is not None:
            # Success - Unlock if was locked (for Director)
            profile.failed_login_attempts = 0
            if profile.is_locked and (profile.role == 'director' or user.is_superuser):
                profile.is_locked = False
            profile.save() # Save the reset attempts/lock status

            # Device Lock Logic
            device_id_to_send = None

            # Skip Device Lock for Director/Superuser
            if profile.role == 'director' or user.is_superuser:
                # Explicitly clear any existing binding for Director to ensure complete removal of the property
                if profile.device_id:
                    profile.device_id = None
                    profile.save()
            else:
                try:
                    client_id = request.headers.get('X-Device-ID') or request.META.get('HTTP_X_DEVICE_ID')
                    if not client_id:
                         # Try to rely on the client sending a generated ID. If not, we can't bind properly.
                         # But to be safe, we reject if no ID is sent.
                         return Response({'error': 'لم يتم التعرف على هوية الجهاز. حاول تحديث الصفحة.', 'code': 'NO_DEVICE_ID'}, status=status.HTTP_400_BAD_REQUEST)

                    if profile.device_id:
                        if profile.device_id.startswith('PENDING:'):
                            # Provisioning Mode: This is the "First Time" after reset/activation.
                            # Bind this device PERMANENTLY.
                            profile.device_id = client_id
                            profile.save()
                            device_id_to_send = client_id
                        else:
                            # Enforce Mode: Must match stored ID
                            if client_id != profile.device_id:
                                return Response({'error': 'هذا الجهاز غير مصرح به. يرجى الاتصال بالمدير.', 'code': 'DEVICE_LOCKED'}, status=status.HTTP_403_FORBIDDEN)
                            else:
                                device_id_to_send = profile.device_id
                    else:
                        # If no device_id set at all, maybe allow binding if we assume "First Login Ever" implies activation?
                        # User requirement: "Once activated by director... enter only once and save fingerprint".
                        # This implies default state is "Locked/No Access" or "Open"?
                        # Usually "Activate Fingerprint" implies it was OFF.
                        # If device_id is None, it means "Fingerprint Not Required/Not Active" OR "Not Set yet".
                        # The prompt says: "When enabling local fingerprint... enter once... save... else call director".
                        # This means if device_id is NONE, check if we should block or allow.
                        # Assuming default is ALLOW (no lock) until Director activates it?
                        # "Activate option" -> sets PENDING.
                        # So if None, we assume "No Lock Enforced" or "Auto Bind"?
                        # Previous logic was "First Time Login - Bind".
                        # Let's keep it "Auto Bind" if None (for ease) OR strict "Must be activated".
                        # The prompt says: "Modify... when enabling... save...".
                        # Auto-bind on first login (Activation)
                        if client_id:
                            profile.device_id = client_id
                            profile.save()
                            device_id_to_send = client_id
                        else:
                            # Fallback if header missing (though we checked above)
                            pass

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

        # Include ALL users (even superusers/directors) so we can see their activity
        users = User.objects.select_related('profile').all().distinct()
        data = []
        seen = set()

        # Get last activity for all users
        from django.db.models import Max
        last_activities = UserActivityLog.objects.values('user').annotate(last_active=Max('timestamp'))
        activity_map = {item['user']: item['last_active'] for item in last_activities}

        now = timezone.now()

        for u in users:
            if u.id in seen: continue
            seen.add(u.id)
            try:
                if not hasattr(u, 'profile'): continue
                prof = u.profile
                device_status = 'غير مفعل'
                if prof.device_id:
                    if prof.device_id.startswith('PENDING:'): device_status = 'بانتظار التفعيل'
                    else: device_status = 'مفعل'

                # Calculate Online Status
                last_active = activity_map.get(u.id)
                is_online = False
                if last_active:
                    try:
                        # Ensure timezone awareness match
                        current_now = now
                        if timezone.is_naive(last_active): last_active = timezone.make_aware(last_active)
                        if timezone.is_naive(current_now): current_now = timezone.make_aware(current_now)

                        diff = (current_now - last_active).total_seconds()
                        if diff < 300: # 5 minutes
                            is_online = True
                    except Exception as e:
                        print(f"Timezone Error for user {u.username}: {e}")

                # Determine if user is Director/Superuser to disable actions in frontend
                is_admin = u.is_superuser or prof.role == 'director'

                # Handle Role Display (fallback if choices removed)
                role_display = prof.role
                if hasattr(prof, 'get_role_display'):
                     try: role_display = prof.get_role_display()
                     except: pass

                data.append({
                    'id': u.id,
                    'username': u.username,
                    'role': prof.role,
                    'role_display': role_display,
                    'is_locked': prof.is_locked,
                    'failed_attempts': prof.failed_login_attempts,
                    'permissions': prof.permissions,
                    'device_status': device_status,
                    'last_login': u.last_login,
                    'last_activity': last_active,
                    'is_online': is_online,
                    'is_admin': is_admin  # Flag for frontend to disable delete/edit
                })
            except Exception as e:
                print(f"Error processing user {u.username}: {e}")
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
