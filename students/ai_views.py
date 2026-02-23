from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Task, TeacherObservation, SchoolMemory
from .serializers import TaskSerializer, TeacherObservationSerializer, SchoolMemorySerializer
from .ai_utils import AIService

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.role == 'director':
            return Task.objects.all()

        # Users see tasks assigned to them OR their role
        role_name = user.profile.role if hasattr(user, 'profile') else None

        return Task.objects.filter(
            Q(assigned_user=user) |
            Q(assigned_role__name=role_name)
        )

    @action(detail=True, methods=['post'])
    def explain(self, request, pk=None):
        task = self.get_object()
        ai = AIService()
        # The user cannot type a custom question here, we force the "Explain" intent
        explanation = ai.generate_response(
            system_instruction=task.manager_instructions or "Explain this task clearly.",
            user_query=f"Explain task: {task.title} - {task.description}"
        )
        return Response({'explanation': explanation})

class TeacherObservationViewSet(viewsets.ModelViewSet):
    queryset = TeacherObservation.objects.all()
    serializer_class = TeacherObservationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.role == 'director':
            return TeacherObservation.objects.all() # Director sees all
        return TeacherObservation.objects.filter(teacher=user)

    @action(detail=True, methods=['post'])
    def consult_ai(self, request, pk=None):
        obs = self.get_object()
        ai = AIService()

        # Guard: Check if observation content is "educational" (Simple Mock Filter)
        if "سيارة" in obs.content or "مباراة" in obs.content:
             return Response({'error': 'عذراً، هذا النظام مخصص للاستشارات التربوية فقط.'}, status=400)

        suggestion = ai.generate_response(
            system_instruction="You are an educational consultant. Provide short, practical advice.",
            user_query=f"Observation about student: {obs.content}"
        )

        obs.ai_suggestion = suggestion
        obs.status = 'ai_suggested'
        obs.save()

        return Response({'suggestion': suggestion})

    @action(detail=True, methods=['post'])
    def approve_suggestion(self, request, pk=None):
        """Teacher approves AI suggestion or submits their own final version"""
        obs = self.get_object()
        final_content = request.data.get('final_content', obs.content) # Default to original if not modified

        obs.final_content = final_content
        obs.status = 'admin_review' # Send to Director
        obs.save()
        return Response({'message': 'Sent to Director for review'})

    @action(detail=True, methods=['post'])
    def admin_action(self, request, pk=None):
        """Director approves (sends) or rejects"""
        if not request.user.profile.role == 'director':
            return Response({'error': 'Unauthorized'}, status=403)

        obs = self.get_object()
        action_type = request.data.get('action') # 'approve' or 'reject'

        if action_type == 'approve':
            obs.status = 'delivered'
            # Here we would actually send SMS/Email to parent
            obs.save()

            # Learn! (Feedback Loop)
            if request.data.get('store_in_memory'):
                SchoolMemory.objects.create(
                    title=f"Solved: {obs.content[:20]}...",
                    content=f"Problem: {obs.content}\nSolution: {obs.final_content}",
                    category='solution'
                )

            return Response({'message': 'Observation delivered to parent.'})

        elif action_type == 'reject':
            obs.status = 'rejected'
            obs.admin_feedback = request.data.get('feedback', '')
            obs.save()
            return Response({'message': 'Returned to teacher.'})

        return Response({'error': 'Invalid action'}, status=400)

class SchoolMemoryViewSet(viewsets.ModelViewSet):
    queryset = SchoolMemory.objects.all()
    serializer_class = SchoolMemorySerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if request.user.profile.role != 'director':
             return Response({'error': 'Unauthorized'}, status=403)
        return super().create(request, *args, **kwargs)
