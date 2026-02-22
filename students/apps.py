from django.apps import AppConfig
import os
from django.conf import settings

class StudentsConfig(AppConfig):
    name = 'students'

    def ready(self):
        # Ensure media directory for photos exists
        try:
            path = os.path.join(settings.MEDIA_ROOT, 'students_photos')
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                print(f"Created photos directory at {path}")
        except Exception as e:
            print(f"Warning: Could not create photos directory: {e}")
