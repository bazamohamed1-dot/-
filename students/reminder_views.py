from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Task
from .ai_utils import AIService
from django.utils import timezone

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_reminders(request):
    """
    Checks for pending tasks and generates AI-flavored reminders.
    This would typically be called by a service worker or a scheduled cron job.
    For this demo, it's an API endpoint the frontend can poll.
    """
    user = request.user
    tasks = Task.objects.filter(assigned_user=user, is_completed=False)

    reminders = []
    ai = AIService()

    for task in tasks:
        # Only remind if due date is close or if it's been a while (simplified logic)
        # Here we just remind for all open tasks for demonstration
        msg = ai.generate_reminder(task.title, task.manager_instructions or "Please complete this task.")
        reminders.append({
            'task_id': task.id,
            'message': msg
        })

    return Response(reminders)
