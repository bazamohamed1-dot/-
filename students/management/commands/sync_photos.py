from django.core.management.base import BaseCommand
from students.models import Student
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Syncs student photos from media/students_photos based on Student ID'

    def handle(self, *args, **options):
        students = Student.objects.all()
        count = 0
        photo_dir = os.path.join(settings.MEDIA_ROOT, 'students_photos')

        if not os.path.exists(photo_dir):
            self.stdout.write(self.style.ERROR(f"Directory not found: {photo_dir}"))
            return

        for student in students:
            # Expected filename
            filename = f"{student.student_id_number}.jpg"
            file_path = os.path.join(photo_dir, filename)

            # Check relative path for DB
            db_path = f"students_photos/{filename}"

            if os.path.exists(file_path):
                # If photo field is empty OR points to something else, update it
                if not student.photo or student.photo.name != db_path:
                    student.photo = db_path
                    student.save()
                    count += 1
                    self.stdout.write(f"Linked photo for {student.last_name} ({student.student_id_number})")

        self.stdout.write(self.style.SUCCESS(f"Successfully synced {count} photos."))
