from django.core.management.base import BaseCommand
from students.models import Student
import os
from django.conf import settings

from students.utils_sync import sync_photos_logic

class Command(BaseCommand):
    help = 'Syncs student photos from media/students_photos based on Student ID'

    def handle(self, *args, **options):
        count = sync_photos_logic()
        self.stdout.write(self.style.SUCCESS(f"Successfully synced {count} photos."))
