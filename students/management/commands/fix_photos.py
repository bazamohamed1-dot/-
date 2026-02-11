from django.core.management.base import BaseCommand
from students.models import Student
from django.conf import settings
import os
import shutil

class Command(BaseCommand):
    help = 'Clears all student photos from database and filesystem for a fresh start'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('⚠️  WARNING: This will delete ALL student photos permanently.'))
        confirm = input('Are you sure you want to proceed? (yes/no): ')

        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Operation cancelled.'))
            return

        # 1. Clear Database Fields
        self.stdout.write('🧹 Cleaning database records...')
        count = Student.objects.update(photo_path=None)
        self.stdout.write(f'   ✅ Updated {count} student records (photos removed).')

        # 2. Delete Physical Files
        photo_dir = os.path.join(settings.MEDIA_ROOT, 'students_photos')
        if os.path.exists(photo_dir):
            self.stdout.write('🗑️  Deleting image files...')
            try:
                shutil.rmtree(photo_dir)
                os.makedirs(photo_dir) # Recreate empty directory
                self.stdout.write('   ✅ Deleted all files in media/students_photos/')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error deleting files: {e}'))
        else:
            self.stdout.write('   ℹ️  Photo directory does not exist, skipping.')

        self.stdout.write(self.style.SUCCESS('\n🎉 Photo system reset complete! You can now upload fresh photos.'))
