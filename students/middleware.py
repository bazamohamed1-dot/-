from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib import messages

class RoleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 1. Single Session Check
            if hasattr(request.user, 'profile'):
                profile = request.user.profile
                session_token = request.session.get('session_token')

                # If session token doesn't match DB (and DB has one), logout
                if profile.active_session_token and session_token != profile.active_session_token:
                    logout(request)
                    messages.error(request, 'تم تسجيل الدخول من جهاز آخر. يرجى تسجيل الدخول مجدداً.')
                    return redirect('login')

            # 2. Role Based Access Control
            if hasattr(request.user, 'profile'):
                role = request.user.profile.role
                path = request.path

                # Skip check for static, admin, login, logout
                if path.startswith('/static/') or path.startswith('/admin/') or path == reverse('login') or path == '/logout/':
                     return self.get_response(request)

                # Director has full access
                if role == 'director':
                    pass

                # Storekeeper -> Canteen
                elif role == 'storekeeper':
                    allowed = ['/ui/', '/canteen', '/scan_card', '/manual_attendance', '/attendance_lists', '/export_canteen']
                    if not any(path.startswith(p) for p in allowed) and path != '/':
                        return redirect('canteen_home')

                # Librarian -> Library
                elif role == 'librarian':
                    allowed = ['/library']
                    if not any(path.startswith(p) for p in allowed) and path != '/':
                        return redirect('library_home')

                # Archivist -> Archive
                elif role == 'archivist':
                    allowed = ['/archive']
                    if not any(path.startswith(p) for p in allowed) and path != '/':
                        # We haven't created the view yet, but will redirect there
                        return redirect('archive_home')

                # Secretariat -> Management
                elif role == 'secretariat':
                    allowed = ['/management', '/list', '/api/students', '/print_cards', '/import_eleve']
                    if not any(path.startswith(p) for p in allowed) and path != '/':
                        return redirect('students_management')

        return self.get_response(request)
