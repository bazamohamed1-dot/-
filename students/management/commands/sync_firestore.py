import os
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from students.models import Student, AttendanceRecord, Communication, PendingUpdate, EmployeeProfile
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Sync data with Firebase Firestore'

    def handle(self, *args, **options):
        # 1. Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            json_path = os.path.join(os.getcwd(), 'baza-school-app-firebase-adminsdk-fbsvc-c29bbfc9a8.json')
            if not os.path.exists(json_path):
                self.stdout.write(self.style.ERROR(f"Firebase Key file not found at: {json_path}"))
                return

            cred = credentials.Certificate(json_path)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        self.stdout.write(self.style.SUCCESS("Connected to Firebase Firestore"))

        # --- PUSH LOGIC (Local -> Cloud) ---

        # 2. Sync Users & Permissions (Full Profile)
        users = User.objects.select_related('profile').all()
        self.stdout.write(f"Pushing {users.count()} users/profiles...")

        batch = db.batch()
        count = 0

        for u in users:
            # Sync to Firestore 'users_profiles'
            # Doc ID = username (unique)
            doc_ref = db.collection('users_profiles').document(u.username)

            role = 'unknown'
            permissions = []
            if hasattr(u, 'profile'):
                role = u.profile.role
                permissions = u.profile.permissions
            elif u.is_superuser:
                role = 'director'
                permissions = ['ALL'] # Special flag

            user_data = {
                'username': u.username,
                'email': u.email,
                'role': role,
                'permissions': permissions,
                'synced_at': firestore.SERVER_TIMESTAMP
            }
            batch.set(doc_ref, user_data, merge=True)

            # Sync to 'allowed_users' for Google Auth check
            if u.email:
                doc_id_email = u.email.replace('@', '_at_').replace('.', '_dot_')
                doc_ref_email = db.collection('allowed_users').document(doc_id_email)
                batch.set(doc_ref_email, user_data, merge=True)

            # Auto-Create/Update Firebase Auth User
            try:
                # Use shadow email for non-google users
                shadow_email = f"{u.username}@bazasystems.com"
                try:
                    fb_user = firebase_auth.get_user_by_email(shadow_email)
                    # Exists, update? (Password can't be retrieved, so skipping pass update here)
                except firebase_auth.UserNotFoundError:
                    self.stdout.write(f"Creating Firebase Auth for {u.username}...")
                    firebase_auth.create_user(
                        email=shadow_email,
                        password="ChangeMe123!", # Default, user should reset or sync via UI
                        display_name=u.username,
                        uid=u.username # Use username as UID for easy mapping
                    )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Auth Sync Warning for {u.username}: {e}"))

            count += 1
            if count >= 400:
                batch.commit()
                batch = db.batch()
                count = 0

        if count > 0:
            batch.commit()

        # 3. Sync Students
        students = Student.objects.all()
        self.stdout.write(f"Pushing {students.count()} students to Cloud...")

        batch = db.batch()
        count = 0
        total_synced = 0

        for s in students:
            doc_ref = db.collection('students').document(str(s.id))
            student_data = {
                'student_id_number': s.student_id_number,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'date_of_birth': s.date_of_birth.strftime('%Y-%m-%d'),
                'class_name': s.class_name,
                'guardian_phone': s.guardian_phone or '',
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            batch.set(doc_ref, student_data, merge=True)
            count += 1
            if count >= 400:
                batch.commit()
                batch = db.batch()
                total_synced += count
                count = 0

        if count > 0:
            batch.commit()

        self.stdout.write(self.style.SUCCESS(f"Finished syncing {total_synced} students."))

        # 4. Sync Attendance (Last 30 Days)
        thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
        attendance_records = AttendanceRecord.objects.filter(date__gte=thirty_days_ago)
        self.stdout.write(f"Pushing {attendance_records.count()} attendance records...")

        batch = db.batch()
        count = 0
        for r in attendance_records:
            doc_id = f"ATT_{r.student.id}_{r.date}_{r.type}"
            doc_ref = db.collection('attendance').document(doc_id)

            att_data = {
                'student_id': str(r.student.id),
                'date': r.date.strftime('%Y-%m-%d'),
                'type': r.type, # 'ABSENT' or 'LATE'
                'reason': r.reason or '',
                'created_at': r.created_at
            }
            batch.set(doc_ref, att_data, merge=True)
            count += 1
            if count >= 400:
                batch.commit()
                batch = db.batch()
                count = 0

        if count > 0:
            batch.commit()

        self.stdout.write(self.style.SUCCESS("Finished syncing attendance."))

        # 5. Sync Communications (Last 30 Days)
        communications = Communication.objects.filter(date__gte=thirty_days_ago)
        self.stdout.write(f"Pushing {communications.count()} messages...")

        batch = db.batch()
        count = 0
        for m in communications:
            doc_id = f"MSG_{m.student.id}_{m.date}_{m.id}"
            doc_ref = db.collection('messages').document(doc_id)

            msg_data = {
                'student_id': str(m.student.id),
                'title': m.title,
                'content': m.content,
                'type': m.type, # 'NOTE', 'SUMMONS', 'INFO'
                'date': m.date.strftime('%Y-%m-%d'),
                'is_read': m.is_read
            }
            batch.set(doc_ref, msg_data, merge=True)
            count += 1
            if count >= 400:
                batch.commit()
                batch = db.batch()
                count = 0

        if count > 0:
            batch.commit()

        self.stdout.write(self.style.SUCCESS("Finished syncing messages."))

        # --- PULL LOGIC (Cloud -> Local) ---

        self.stdout.write("Checking for pending updates from Employees...")
        pending_ref = db.collection('pending_updates').where('status', '==', 'pending')
        docs = pending_ref.stream()

        pulled_count = 0
        for doc in docs:
            data = doc.to_dict()
            firestore_id = doc.id

            try:
                PendingUpdate.objects.create(
                    user=None, # System created
                    model_name=data.get('type', 'UNKNOWN'),
                    action='create',
                    data=data, # Store the whole JSON
                    status='pending',
                    timestamp=timezone.now()
                )

                doc.reference.update({'status': 'reviewing'})
                pulled_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error pulling doc {firestore_id}: {str(e)}"))

        if pulled_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully pulled {pulled_count} new updates for review."))
        else:
            self.stdout.write("No new pending updates found.")
