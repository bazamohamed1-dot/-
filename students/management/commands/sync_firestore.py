import os
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
import firebase_admin
from firebase_admin import credentials, firestore
from students.models import Student, AttendanceRecord, Communication, PendingUpdate

class Command(BaseCommand):
    help = 'Sync data with Firebase Firestore'

    def handle(self, *args, **options):
        # 1. Initialize Firebase Admin SDK
        # Check if already initialized to avoid error
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

        # 2. Sync Students (Active only, or all)
        # We assume `active` is implicit or handled by status. I'll just sync all for now.
        students = Student.objects.all()
        self.stdout.write(f"Pushing {students.count()} students to Cloud...")

        # Batch write in chunks of 400
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
                self.stdout.write(f"  ... synced {total_synced} students")

        if count > 0:
            batch.commit()
            total_synced += count

        self.stdout.write(self.style.SUCCESS(f"Finished syncing {total_synced} students."))

        # 3. Sync Attendance (Last 30 Days)
        thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
        attendance_records = AttendanceRecord.objects.filter(date__gte=thirty_days_ago)
        self.stdout.write(f"Pushing {attendance_records.count()} attendance records...")

        batch = db.batch()
        count = 0
        for r in attendance_records:
            # Create a unique ID for the document
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

        # 4. Sync Communications (Last 30 Days)
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
        # Stream allows iterating over large datasets without loading all into memory
        docs = pending_ref.stream()

        pulled_count = 0
        for doc in docs:
            data = doc.to_dict()
            firestore_id = doc.id

            # Create a local PendingUpdate record
            # We store the raw data so the Director can review it
            try:
                PendingUpdate.objects.create(
                    user=None, # System created
                    model_name=data.get('type', 'UNKNOWN'),
                    action='create',
                    data=data, # Store the whole JSON
                    status='pending',
                    timestamp=timezone.now()
                )

                # Update status in Firestore to 'reviewing' so we don't pull it again
                doc.reference.update({'status': 'reviewing'})
                pulled_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error pulling doc {firestore_id}: {str(e)}"))

        if pulled_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully pulled {pulled_count} new updates for review."))
        else:
            self.stdout.write("No new pending updates found.")
