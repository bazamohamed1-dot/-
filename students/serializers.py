from rest_framework import serializers
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, SystemMessage, UserRole, PendingUpdate
from django.conf import settings
from django.core.files.base import ContentFile
import uuid
import base64
import os
from PIL import Image
from io import BytesIO

class Base64ImageField(serializers.ImageField):
    """
    A Django REST framework field for handling image-uploads through raw post data.
    It uses base64 for encoding and decoding the contents of the file.
    """
    def to_internal_value(self, data):
        # Check if this is a base64 string
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                # Format: "data:image/jpeg;base64,..."
                header, encoded = data.split(';base64,')
                ext = header.split('/')[-1]
                if ext == 'jpeg': ext = 'jpg'

                # Decode
                decoded_file = base64.b64decode(encoded)

                # Resize and Optimize
                img = Image.open(BytesIO(decoded_file))
                img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)

                # Force Convert to RGB/JPEG for consistency
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                output = BytesIO()
                img.save(output, format='JPEG', quality=95)
                output.seek(0)

                file_name = f"temp.jpg" # Name doesn't matter, model upload_to handles it
                data = ContentFile(output.read(), name=file_name)

            except Exception as e:
                print(f"Base64 Decode Error: {e}")
                self.fail('invalid_image')

        return super().to_internal_value(data)

class StudentSerializer(serializers.ModelSerializer):
    photo = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Student
        fields = '__all__'

class StudentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing students.
    """
    class Meta:
        model = Student
        fields = [
            'id', 'student_id_number', 'first_name', 'last_name',
            'class_name', 'academic_year', 'gender', 'date_of_birth',
            'place_of_birth', 'attendance_system', 'enrollment_date',
            'enrollment_number', 'exit_date', 'guardian_name', 'mother_name',
            'guardian_phone', 'address', 'photo'
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
