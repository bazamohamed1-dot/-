from django.core.management.base import BaseCommand
from students.models import Student
from django.conf import settings
import cloudinary
import cloudinary.uploader
import uuid

class Command(BaseCommand):
    help = 'Migrates existing Base64 images to Cloudinary to reduce database size'

    def handle(self, *args, **options):
        # Configure Cloudinary using settings
        try:
            cloudinary.config(
                cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Cloudinary Configuration Error: {e}"))
            return

        students = Student.objects.all()
        processed_count = 0
        migrated_count = 0
        error_count = 0

        self.stdout.write("Starting image migration...")

        for student in students:
            processed_count += 1
            photo_path = student.photo_path

            # Check if photo_path looks like a Base64 string (starts with data:image or is very long)
            # Normal URL is usually short (< 200 chars). Base64 image is usually > 1000 chars.
            if photo_path and len(photo_path) > 500:
                # Basic check for Base64 pattern or just length
                is_base64 = photo_path.strip().startswith('data:image') or ';base64,' in photo_path

                if is_base64 or len(photo_path) > 2000: # Heuristic: if extremely long, treat as base64
                    try:
                        self.stdout.write(f"Migrating image for student: {student.student_id_number}")

                        # Generate a unique public ID
                        public_id = f"student_{student.student_id_number}_{uuid.uuid4().hex[:8]}"

                        # Upload
                        upload_result = cloudinary.uploader.upload(
                            photo_path,
                            folder="students_photos",
                            public_id=public_id,
                            resource_type="image"
                        )

                        # Update DB
                        new_url = upload_result.get('secure_url')
                        if new_url:
                            student.photo_path = new_url
                            student.save()
                            migrated_count += 1
                            self.stdout.write(self.style.SUCCESS(f" -> Success: {new_url}"))
                        else:
                            self.stdout.write(self.style.ERROR(" -> Upload failed (no URL returned)"))
                            error_count += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f" -> Error: {str(e)}"))
                        error_count += 1

            if processed_count % 50 == 0:
                self.stdout.write(f"Processed {processed_count} students...")

        self.stdout.write(self.style.SUCCESS(f"Migration Complete.\nProcessed: {processed_count}\nMigrated: {migrated_count}\nErrors: {error_count}"))
