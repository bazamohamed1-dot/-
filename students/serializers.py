from rest_framework import serializers
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, SystemMessage, UserRole
from django.conf import settings
import uuid
import base64
import os

def save_base64_image(image_data, student_id):
    """
    Saves a base64 encoded image to the local media directory.
    Returns the relative path to be stored in the DB.
    """
    if not image_data or not str(image_data).startswith('data:image'):
        return image_data # Return as is if it's already a path or invalid

    try:
        # Format: "data:image/jpeg;base64,..."
        header, encoded = str(image_data).split(',', 1)
        extension = header.split('/')[1].split(';')[0] # e.g., jpeg

        filename = f"student_{student_id}_{uuid.uuid4().hex[:8]}.{extension}"
        relative_path = os.path.join('students_photos', filename)
        full_path = os.path.join(settings.MEDIA_ROOT, 'students_photos', filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as fh:
            fh.write(base64.b64decode(encoded))

        return relative_path
    except Exception as e:
        print(f"Image Save Error: {e}")
        return None

class StudentSerializer(serializers.ModelSerializer):
    # Use method field to generate full URL for frontend
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'

    def get_photo_url(self, obj):
        if obj.photo_path:
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
                saved_path = save_base64_image(new_photo, instance.student_id_number)
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
