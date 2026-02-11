from django.apps import AppConfig

class StudentsConfig(AppConfig):
    name = 'students'

    def ready(self):
        # Cloudinary config removed for local version
        pass
