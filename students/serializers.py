from rest_framework import serializers
from .models import Student, CanteenAttendance, LibraryLoan, SchoolSettings, ArchiveDocument, PendingUpdate, SystemMessage, UserRole

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
