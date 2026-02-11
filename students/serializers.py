from rest_framework import serializers
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, PendingUpdate, SystemMessage, UserRole
import cloudinary
import cloudinary.uploader
from django.conf import settings
import uuid

def upload_image_to_cloudinary(image_data, student_id):
    if not image_data or len(str(image_data)) < 500: # Assuming URL < 500 chars, Base64 >> 500
        return image_data

    try:
        # Configure Cloudinary if needed
        if not cloudinary.config().cloud_name:
             cloudinary.config(
                cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
            )

        public_id = f"student_{student_id}_{uuid.uuid4().hex[:8]}"
        response = cloudinary.uploader.upload(
            image_data,
            folder="students_photos",
            public_id=public_id,
            resource_type="image"
        )
        return response.get('secure_url', image_data)
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return image_data # Fallback

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

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'

    def create(self, validated_data):
        if 'photo_path' in validated_data:
            student_id = validated_data.get('student_id_number', 'unknown')
            validated_data['photo_path'] = upload_image_to_cloudinary(validated_data['photo_path'], student_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'photo_path' in validated_data:
            new_photo = validated_data['photo_path']
            # Only upload if changed and is long (Base64)
            if new_photo != instance.photo_path and len(str(new_photo)) > 500:
                validated_data['photo_path'] = upload_image_to_cloudinary(new_photo, instance.student_id_number)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """
        Dynamically optimize Cloudinary URLs for listing to save bandwidth and memory.
        """
        ret = super().to_representation(instance)
        photo_path = ret.get('photo_path')

        # Check if it's a valid Cloudinary URL
        if photo_path and 'res.cloudinary.com' in photo_path and '/upload/' in photo_path:
            try:
                # Inject transformation: w_400,h_400,c_limit,q_auto,f_auto
                # Example: .../upload/v1234/student.jpg -> .../upload/w_400,c_limit,q_auto,f_auto/v1234/student.jpg
                parts = photo_path.split('/upload/')
                if len(parts) == 2:
                    ret['photo_path'] = f"{parts[0]}/upload/w_400,c_limit,q_auto,f_auto/{parts[1]}"
            except Exception:
                pass # Return original if splitting fails

        return ret

class StudentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing students (No heavy photo data).
    """
    class Meta:
        model = Student
        exclude = ['photo_path']

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
