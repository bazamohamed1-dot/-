from django.apps import AppConfig
import cloudinary
import os

class StudentsConfig(AppConfig):
    name = 'students'

    def ready(self):
        # Configure Cloudinary
        try:
            cloudinary.config(
                cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                api_key=os.getenv('CLOUDINARY_API_KEY'),
                api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                secure=True
            )
        except Exception as e:
            print(f"Cloudinary Config Error: {e}")
