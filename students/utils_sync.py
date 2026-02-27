import os
from django.conf import settings
from .models import Student

def sync_photos_logic():
    """
    Core logic to link students with photos in media/students_photos.
    Returns the count of updated records.
    """
    students = Student.objects.all()
    count = 0
    photo_dir = os.path.join(settings.MEDIA_ROOT, 'students_photos')

    if not os.path.exists(photo_dir):
        return 0

    for student in students:
        filename = f"{student.student_id_number}.jpg"
        file_path = os.path.join(photo_dir, filename)
        db_path = f"students_photos/{filename}"

        if os.path.exists(file_path):
            if not student.photo or student.photo.name != db_path:
                student.photo = db_path
                student.save()
                count += 1
    return count
