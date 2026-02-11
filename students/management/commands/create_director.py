from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from students.models import EmployeeProfile
import sys

class Command(BaseCommand):
    help = 'Create a Director account interactively'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🛠️  Create Director Account'))

        # Username
        while True:
            username = input('Enter Username (default: director): ').strip()
            if not username:
                username = 'director'

            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.ERROR(f'User "{username}" already exists. Try another name.'))
                continue
            break

        # Password
        while True:
            password = input('Enter Password: ').strip()
            if not password:
                self.stdout.write(self.style.ERROR('Password cannot be empty.'))
                continue

            confirm = input('Confirm Password: ').strip()
            if password != confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue
            break

        try:
            # Create User
            user = User.objects.create_superuser(username=username, email='', password=password)

            # Create Profile
            profile, created = EmployeeProfile.objects.get_or_create(user=user)
            profile.role = 'director'
            profile.is_locked = False
            # Add all permissions just in case
            profile.permissions = [
                'canteen_scan', 'canteen_manual', 'canteen_export',
                'library_scan', 'library_loan', 'library_return', 'library_readers_list',
                'student_add', 'student_edit', 'student_delete', 'import_data'
            ]
            profile.save()

            self.stdout.write(self.style.SUCCESS(f'\n✅ Director account "{username}" created successfully!'))
            self.stdout.write(self.style.SUCCESS('You can now log in using these credentials.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {e}'))
