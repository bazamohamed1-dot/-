from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import EmployeeProfile, UserActivityLog, SchoolSettings, UserRole
from .serializers import UserRoleSerializer
from .auth_utils import send_password_reset_email, generate_random_password, send_new_account_email
import secrets
import pyotp
import qrcode
import base64
from io import BytesIO
import os
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

# --- Firebase Helper ---
def sync_user_to_firebase(username, password=None, is_active=True):
    """Syncs a local user to Firebase Auth."""
    try:
        # Initialize if needed
        if not firebase_admin._apps:
            json_path = os.path.join(os.getcwd(), 'baza-school-app-firebase-adminsdk-fbsvc-c29bbfc9a8.json')
            if os.path.exists(json_path):
                cred = credentials.Certificate(json_path)
                firebase_admin.initialize_app(cred)
            else:
                return # Skip if no key

        email = f"{username}@bazasystems.com"

        # Check if user exists
        try:
            user = firebase_auth.get_user_by_email(email)
            # Update password if provided
            if password:
                firebase_auth.update_user(user.uid, password=password, disabled=(not is_active))
            else:
                firebase_auth.update_user(user.uid, disabled=(not is_active))
        except firebase_auth.UserNotFoundError:
            if is_active:
                # Create user
                firebase_auth.create_user(
                    email=email,
                    password=password or "TemporaryPass123!", # Should ideally be synced
                    display_name=username,
                    disabled=False
                )
    except Exception as e:
        print(f"Firebase Sync Error: {e}")

def delete_user_from_firebase(username):
    try:
        if not firebase_admin._apps: return
        email = f"{username}@bazasystems.com"
        user = firebase_auth.get_user_by_email(email)
        firebase_auth.delete_user(user.uid)
    except:
        pass

# --- 2FA Views ---
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
            'username': user.username,
            'must_change_password': profile.must_change_password
        })
    else:
        return Response({'error': 'رمز خاطئ'}, status=400)

# --- Forgot Password Views ---
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    # Backward compatibility + New Logic
    username = request.data.get('username')
    email = request.data.get('email')

    # If email provided, use new flow
    if email:
        user = User.objects.filter(email=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            full_token = f"{uid}-{token}"
            try:
                send_password_reset_email(user, full_token)
            except Exception as e:
                pass
        return Response({'message': 'تم إرسال رابط الاستعادة إذا كان البريد مسجلاً.'})

    # Legacy Director Flow
    settings_obj = SchoolSettings.objects.first()
    admin_email = settings_obj.admin_email if settings_obj else None

    if username:
        try:
            user = User.objects.get(username=username)
            if (hasattr(user, 'profile') and user.profile.role == 'director') or user.is_superuser:
                if not admin_email:
                    return Response({'error': 'لم يتم إعداد بريد استرجاع (Admin Email).'}, status=400)

                token = secrets.token_hex(4)
                settings_obj.recovery_token = token
                settings_obj.recovery_token_created_at = timezone.now()
                settings_obj.save()

                # Send via Email (SMTP now works!)
                send_mail(
                    'Director Recovery Code',
                    f'Your recovery code is: {token}',
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=True
                )

                return Response({'message': f'تم إرسال رمز الاستعادة إلى {admin_email}.'})
        except User.DoesNotExist:
            pass

    return Response({'message': 'إذا كان الحساب صحيحاً، فقد تم الإرسال.'})

class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        return forgot_password(request) # Reuse logic

class ConfirmPasswordResetView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        token_str = request.data.get('token')
        password = request.data.get('password')

        if not token_str or not password:
            return Response({'error': 'Token and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if '-' not in token_str: return Response({'error': 'Invalid token'}, status=400)
            uid_b64, token = token_str.split('-', 1)
            uid = force_str(urlsafe_base64_decode(uid_b64))
            user = User.objects.get(pk=uid)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid link'}, status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({'message': 'Password has been reset successfully.'})
        else:
            return Response({'error': 'Link is invalid or expired'}, status=status.HTTP_400_BAD_REQUEST)

class ForceChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        password = request.data.get('new_password')
        if not password:
             return Response({'error': 'New password is required'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.set_password(password)
        if hasattr(user, 'profile'):
            user.profile.must_change_password = False
            user.profile.save()
        user.save()

        # Sync to Firebase
        sync_user_to_firebase(user.username, password)

        return Response({'message': 'Password changed successfully.'})

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

        # --- Director Recovery Login ---
        settings_obj = SchoolSettings.objects.first()
        if settings_obj and settings_obj.admin_email and username.strip().lower() == settings_obj.admin_email.strip().lower():
            if settings_obj.recovery_token and password.strip() == settings_obj.recovery_token:
                settings_obj.recovery_token = None
                settings_obj.save()

                director_profile = EmployeeProfile.objects.filter(role='director').first()
                target_user = director_profile.user if director_profile else User.objects.filter(is_superuser=True).first()

                if target_user:
                     profile = target_user.profile
                     profile.failed_login_attempts = 0
                     profile.is_locked = False

                     token = secrets.token_hex(32)
                     profile.current_session_token = token
                     profile.must_change_password = True # Force change
                     profile.save()

                     login(request, target_user)
                     UserActivityLog.objects.create(user=target_user, action='login_recovery_token')

                     return Response({
                        'message': 'Logged in via recovery.',
                        'token': token,
                        'role': profile.role,
                        'username': target_user.username,
                        'must_change_password': True
                    })
            else:
                return Response({'error': 'Invalid recovery code'}, status=400)

        # --- Standard Login ---
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(user, 'profile'):
            role = 'director' if user.is_superuser else 'secretariat'
            EmployeeProfile.objects.create(user=user, role=role)

        profile = user.profile

        if profile.is_locked and profile.role != 'director':
            return Response({'error': 'Account Locked', 'code': 'LOCKED'}, status=status.HTTP_403_FORBIDDEN)

        user_auth = authenticate(username=username, password=password)

        if user_auth is not None:
            profile.failed_login_attempts = 0
            if profile.is_locked: profile.is_locked = False
            profile.save()

            # Device Lock Check
            device_id_to_send = None
            if profile.role != 'director' and not user.is_superuser:
                client_id = request.headers.get('X-Device-ID')
                if client_id:
                     if not profile.device_id or profile.device_id.startswith('PENDING:'):
                         profile.device_id = client_id
                         profile.save()
                         device_id_to_send = client_id
                     elif profile.device_id != client_id:
                         return Response({'error': 'Unauthorized Device', 'code': 'DEVICE_LOCKED'}, status=403)
                     else:
                         device_id_to_send = profile.device_id

            if profile.totp_enabled:
                temp_token = secrets.token_hex(16)
                profile.current_session_token = f"PRE-2FA:{temp_token}"
                profile.save()
                return Response({'require_2fa': True, 'temp_token': temp_token})

            token = secrets.token_hex(32)
            profile.current_session_token = token
            profile.save()

            login(request, user)
            UserActivityLog.objects.create(user=user, action='login')

            return Response({
                'message': 'Login Successful',
                'token': token,
                'role': profile.role,
                'username': user.username,
                'device_id': device_id_to_send,
                'must_change_password': profile.must_change_password
            })
        else:
            profile.failed_login_attempts += 1
            if profile.failed_login_attempts >= 3:
                profile.is_locked = True
                profile.save()
                return Response({'error': 'Account Locked', 'code': 'LOCKED'}, status=403)
            profile.save()
            return Response({'error': 'Invalid Credentials', 'code': 'INVALID_CREDS'}, status=400)

    except Exception as e:
        return Response({'error': f'Server Error: {str(e)}'}, status=500)

@api_view(['POST'])
def verify_session(request):
    token = request.data.get('token')
    if not request.user.is_authenticated:
        return Response({'valid': False, 'reason': 'NOT_LOGGED_IN'}, status=401)
    try:
        if request.user.profile.current_session_token == token:
            return Response({'valid': True, 'role': request.user.profile.role})
    except: pass
    return Response({'valid': False}, status=401)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([]) # Disable auth checks for this view
@permission_classes([AllowAny])
def logout_view(request):
    if request.user.is_authenticated:
        try:
            request.user.profile.current_session_token = None
            request.user.profile.save()
        except: pass
        logout(request)

    response = Response({'message': 'Logged out'})
    # Explicitly clear cookies to fix loop issues
    response.delete_cookie('baza_school_session_v2')
    response.delete_cookie('baza_school_csrf_v2')
    response.delete_cookie('sessionid')
    response.delete_cookie('csrftoken')
    return response

class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def check_permission(self, request, perm):
        if not hasattr(request.user, 'profile'): return False
        return request.user.profile.has_perm(perm)

    def list(self, request):
        if not self.check_permission(request, 'manage_users'):
            return Response({'error': 'Unauthorized'}, status=403)

        # Include ALL users
        users = User.objects.select_related('profile').all().distinct()
        data = []
        seen = set()

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

                last_active = activity_map.get(u.id)
                is_online = False
                if last_active:
                    try:
                        current_now = now
                        if timezone.is_naive(last_active): last_active = timezone.make_aware(last_active)
                        if timezone.is_naive(current_now): current_now = timezone.make_aware(current_now)

                        diff = (current_now - last_active).total_seconds()
                        if diff < 300: # 5 minutes
                            is_online = True
                    except Exception as e:
                        pass

                is_admin = u.is_superuser or prof.role == 'director'

                data.append({
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'role': prof.role,
                    'is_locked': prof.is_locked,
                    'failed_attempts': prof.failed_login_attempts,
                    'permissions': prof.permissions,
                    'is_active_cloud': prof.is_active_cloud,
                    'assigned_interface': prof.assigned_interface,
                    'device_status': device_status,
                    'last_login': u.last_login,
                    'last_activity': last_active,
                    'is_online': is_online,
                    'is_admin': is_admin
                })
            except Exception as e:
                pass
        return Response(data)

    def create(self, request):
        if not self.check_permission(request, 'manage_users'):
            return Response({'error': 'Unauthorized'}, status=403)

        username = request.data.get('username')
        role = request.data.get('role')
        email = request.data.get('email', '')
        permissions = request.data.get('permissions', [])

        is_active_cloud = request.data.get('is_active_cloud', True)
        assigned_interface = request.data.get('assigned_interface', 'all')

        password = request.data.get('password')

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username exists'}, status=400)

        if not password:
             password = generate_random_password()

        user = User.objects.create_user(username=username, password=password, email=email)
        EmployeeProfile.objects.create(
            user=user,
            role=role,
            permissions=permissions,
            is_active_cloud=is_active_cloud,
            assigned_interface=assigned_interface,
            must_change_password=True
        )

        sync_user_to_firebase(username, password, is_active=is_active_cloud)

        try:
            sent = send_new_account_email(user, password)
            msg = 'User created. Credentials sent via email.' if sent else 'User created. Failed to send email.'
        except:
            msg = 'User created, but email failed.'

        return Response({'message': msg})

    def destroy(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        if user == request.user or user.is_superuser: return Response({'error': 'Cannot delete'}, status=400)

        username = user.username
        user.delete()

        delete_user_from_firebase(username)

        return Response({'message': 'User deleted'})

    @action(detail=True, methods=['post'])
    def update_creds(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        new_pass = request.data.get('password')
        permissions = request.data.get('permissions')
        role = request.data.get('role')
        email = request.data.get('email')

        is_active_cloud = request.data.get('is_active_cloud')
        assigned_interface = request.data.get('assigned_interface')

        if new_pass:
            user.set_password(new_pass)
            sync_user_to_firebase(user.username, new_pass, is_active=is_active_cloud if is_active_cloud is not None else user.profile.is_active_cloud)

        if email is not None:
             user.email = email

        user.save()

        if permissions is not None: user.profile.permissions = permissions
        if role: user.profile.role = role
        if is_active_cloud is not None:
            user.profile.is_active_cloud = is_active_cloud
            # Sync status change only if password wasn't synced above
            if not new_pass:
                sync_user_to_firebase(user.username, password=None, is_active=is_active_cloud)

        if assigned_interface: user.profile.assigned_interface = assigned_interface

        user.profile.save()
        return Response({'message': 'Updated'})

    @action(detail=True, methods=['post'])
    def unlock_account(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        user.profile.is_locked = False
        user.profile.failed_login_attempts = 0
        user.profile.save()
        return Response({'message': 'Unlocked'})

    @action(detail=True, methods=['post'])
    def reset_session(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        user.profile.current_session_token = None
        user.profile.save()
        return Response({'message': 'Session Reset'})

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
        return Response({'message': 'Device Activated'})

    @action(detail=True, methods=['post'])
    def reset_device(self, request, pk=None):
        if not self.check_permission(request, 'manage_users'): return Response({'error': 'Unauthorized'}, status=403)
        user = self.get_object()
        user.profile.device_id = None
        user.profile.save()
        return Response({'message': 'Device Reset'})
