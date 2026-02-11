from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PendingUpdate, Student, CanteenAttendance, LibraryLoan, SystemMessage
from .serializers import PendingUpdateSerializer, SystemMessageSerializer
# Cloudinary removed
from datetime import date
import logging
import base64
import os
import uuid
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

class SyncViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        # Expects a list of offline requests
        items = request.data
        if not isinstance(items, list):
            items = [items]

        count = 0
        for item in items:
            url = item.get('url', '')
            method = item.get('method', 'POST')

            # Map URL to Model
            model_name = 'Unknown'
            action_type = 'create'

            if 'students' in url:
                model_name = 'Student'
                if method == 'PUT' or method == 'PATCH': action_type = 'update'
                elif method == 'DELETE': action_type = 'delete'
                elif 'bulk_delete' in url: action_type = 'delete'
            elif 'scan_card' in url or 'manual_attendance' in url:
                model_name = 'CanteenAttendance'
            elif 'loan' in url:
                model_name = 'LibraryLoan'

            PendingUpdate.objects.create(
                user=request.user,
                model_name=model_name,
                action=action_type,
                data=item # Store full item
            )
            count += 1

        return Response({'message': f'Synced {count} items'})

class PendingUpdateViewSet(viewsets.ModelViewSet):
    queryset = PendingUpdate.objects.all().order_by('-timestamp')
    serializer_class = PendingUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'profile') and (self.request.user.profile.role == 'director' or self.request.user.is_superuser):
            return PendingUpdate.objects.all()
        return PendingUpdate.objects.none()

    def _apply_update(self, update):
        data_payload = update.data.get('data', {})

        if update.model_name == 'Student':
            # Handle Photo - Save Locally
            photo_data = data_payload.get('photo_path')
            if photo_data and str(photo_data).startswith('data:image'):
                try:
                    format, imgstr = photo_data.split(';base64,')
                    ext = format.split('/')[-1]
                    filename = f"{uuid.uuid4()}.{ext}"
                    filepath = os.path.join(settings.MEDIA_ROOT, 'students_photos', filename)

                    os.makedirs(os.path.dirname(filepath), exist_ok=True)

                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(imgstr))

                    # Store relative path or URL
                    data_payload['photo_path'] = f"/media/students_photos/{filename}"
                except Exception as e:
                    logger.error(f"Image Save Error: {e}")
                    # Continue without photo
                    pass

            if update.action == 'create':
                valid_fields = [f.name for f in Student._meta.get_fields() if f.name != 'id']
                clean_data = {k: v for k, v in data_payload.items() if k in valid_fields}
                Student.objects.create(**clean_data)

            elif update.action == 'update':
                # Extract ID from URL
                # url format: /api/students/123/
                try:
                    obj_id = update.data.get('url', '').rstrip('/').split('/')[-1]
                    if obj_id.isdigit():
                        obj = Student.objects.get(id=obj_id)
                        valid_fields = [f.name for f in Student._meta.get_fields() if f.name != 'id']
                        for k, v in data_payload.items():
                            if k in valid_fields:
                                setattr(obj, k, v)
                        obj.save()
                except Student.DoesNotExist:
                    pass

            elif update.action == 'delete':
                try:
                    # Check if bulk delete (POST to bulk_delete endpoint)
                    if 'bulk_delete' in update.data.get('url', ''):
                        ids = data_payload.get('ids', [])
                        if ids:
                            Student.objects.filter(id__in=ids).delete()
                    else:
                        obj_id = update.data.get('url', '').rstrip('/').split('/')[-1]
                        if obj_id.isdigit():
                            Student.objects.filter(id=obj_id).delete()
                except:
                    pass

        elif update.model_name == 'CanteenAttendance':
            barcode = data_payload.get('barcode') or data_payload.get('student_id')
            student = None
            if barcode:
                student = Student.objects.filter(student_id_number=barcode).first()
                if not student and str(barcode).isdigit():
                        student = Student.objects.filter(id=barcode).first()

            if student:
                if not CanteenAttendance.objects.filter(student=student, date=date.today()).exists():
                        CanteenAttendance.objects.create(student=student, date=date.today())

        update.delete()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        update = self.get_object()
        try:
            self._apply_update(update)
            return Response({'message': 'Approved'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def approve_all(self, request):
        updates = self.get_queryset()
        count = 0
        errors = []
        for update in updates:
             try:
                self._apply_update(update)
                count += 1
             except Exception as e:
                errors.append(f"ID {update.id}: {str(e)}")

        return Response({'message': f'Approved {count}', 'errors': errors})

    @action(detail=False, methods=['post'])
    def reject_all(self, request):
        self.get_queryset().delete()
        return Response({'message': 'Rejected All'})

    @action(detail=False, methods=['get'])
    def count(self, request):
        count = self.get_queryset().count()
        return Response({'count': count})

class SystemMessageViewSet(viewsets.ModelViewSet):
    queryset = SystemMessage.objects.filter(active=True)
    serializer_class = SystemMessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'director':
            serializer.save()
        else:
            raise PermissionError("Only Director can create messages")
