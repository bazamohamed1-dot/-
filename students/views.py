from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Student
from .serializers import StudentSerializer
from django.db import models # استيراد models هنا لاستخدام Q objects

def index(request):
    return render(request, 'students/index.html')

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    @action(detail=False, methods=['GET'])
    def search_by_name(self, request):
        query = request.query_params.get('name', '')
        if query:
            students = Student.objects.filter(
                models.Q(first_name__icontains=query) | models.Q(last_name__icontains=query)
            )
            serializer = self.get_serializer(students, many=True)
            return Response(serializer.data)
        return Response({"message": "يرجى تقديم اسم للبحث عنه."}, status=status.HTTP_400_BAD_REQUEST)

