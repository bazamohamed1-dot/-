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
                prof = u.profile
                device_status = 'غير مفعل'
                if prof.device_id:
                    if prof.device_id.startswith('PENDING:'): device_status = 'بانتظار التفعيل'
                    else: device_status = 'مفعل'

                # Calculate Online Status
                last_active = activity_map.get(u.id)
                is_online = False
                if last_active:
                    diff = (now - last_active).total_seconds()
                    if diff < 300: # 5 minutes
                        is_online = True

                # Determine if user is Director/Superuser to disable actions in frontend
                is_admin = u.is_superuser or prof.role == 'director'

                data.append({
                    'id': u.id,
                    'username': u.username,
                    'role': prof.role,
                    'role_display': prof.get_role_display(),
                    'is_locked': prof.is_locked,
                    'failed_attempts': prof.failed_login_attempts,
                    'permissions': prof.permissions,
                    'device_status': device_status,
                    'last_login': u.last_login,
                    'last_activity': last_active,
                    'is_online': is_online,
                    'is_admin': is_admin  # Flag for frontend to disable delete/edit
                })
            except:
                pass
        return Response(data)
