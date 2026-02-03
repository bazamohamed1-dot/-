from rest_framework import serializers
from .models import Student

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__' 
    
    def validate(self, data):
        phone = data.get('guardian_phone', None)
        if not phone or not phone.strip():
             raise serializers.ValidationError("رقم هاتف الولي إجباري ولا يمكن أن يكون فارغاً.")
        return data
