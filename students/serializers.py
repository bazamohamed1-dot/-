from rest_framework import serializers
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, SystemMessage, UserRole, PendingUpdate
from django.conf import settings
import uuid
import base64
import os
from PIL import Image
from io import BytesIO

def save_base64_image(image_data, student_id):
    """
    Saves a base64 encoded image to the local media directory.
    - Resizes to max 1000x1000 pixels.
    - Converts to JPEG format (Quality 95).
    - Renames to {student_id}.jpg.
    Returns the relative path to be stored in the DB.
    """
    if not image_data or not str(image_data).startswith('data:image'):
        return image_data # Return as is if it's already a path or invalid

    try:
        # Format: "data:image/jpeg;base64,..."
        header, encoded = str(image_data).split(',', 1)

        # Decode
        image_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(image_bytes))

        # Resize (Thumbnail maintains aspect ratio)
        img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)

        # Convert to RGB (in case of PNG/RGBA)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Filename: {student_id}.jpg
        # Sanitize student_id to be safe filename
        safe_id = str(student_id).strip().replace('/', '_').replace('\\', '_')
        filename = f"{safe_id}.jpg"

        relative_path = os.path.join('students_photos', filename)
        full_path = os.path.join(settings.MEDIA_ROOT, 'students_photos', filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save (Overwrite if exists)
        img.save(full_path, "JPEG", quality=95)

        return relative_path
    except Exception as e:
        print(f"Image Save Error: {e}")
        # Return the original data if save fails, so we don't lose the photo string
        # This allows re-trying or debugging
        return image_data

class StudentSerializer(serializers.ModelSerializer):
    # Use method field to generate full URL for frontend
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'

    def get_photo_url(self, obj):
        if obj.photo_path:
            # Append timestamp to bust cache if needed?
            # For now, let's stick to standard URL. Frontend can handle cache busting if needed.
            return f"{settings.MEDIA_URL}{obj.photo_path}"
        return None

    def create(self, validated_data):
        if 'photo_path' in validated_data:
            student_id = validated_data.get('student_id_number', 'unknown')
            # If it's base64, save it locally
            validated_data['photo_path'] = save_base64_image(validated_data['photo_path'], student_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'photo_path' in validated_data:
            new_photo = validated_data['photo_path']
            # If changed and is base64
            if new_photo != instance.photo_path and str(new_photo).startswith('data:image'):
                # Use new ID if changed, else old
                sid = validated_data.get('student_id_number', instance.student_id_number)
                saved_path = save_base64_image(new_photo, sid)
                if saved_path:
                    validated_data['photo_path'] = saved_path
        return super().update(instance, validated_data)

class StudentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing students.
    """
    class Meta:
        model = Student
        # Exclude heavy fields if necessary, but keep basic info
        # Added: place_of_birth, attendance_system, enrollment_date, photo_path to support management UI
        fields = [
            'id', 'student_id_number', 'first_name', 'last_name',
            'class_name', 'academic_year', 'gender', 'date_of_birth',
            'place_of_birth', 'attendance_system', 'enrollment_date',
            'enrollment_number', 'exit_date', 'guardian_name', 'mother_name',
            'guardian_phone', 'address', 'photo_path'
        ]

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'

class PendingUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = PendingUpdate
        fields = '__all__'

class SystemMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMessage
        fields = '__all__'

class ArchiveDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveDocument
        fields = '__all__'

class CanteenAttendanceSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    class Meta:
        model = CanteenAttendance
        fields = '__all__'

class LibraryLoanSerializer(serializers.ModelSerializer):
    student_details = StudentSerializer(source='student', read_only=True)
    class Meta:
        model = LibraryLoan
        fields = '__all__'

class SchoolSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolSettings
        fields = '__all__'
