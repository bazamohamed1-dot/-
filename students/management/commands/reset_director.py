from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from students.models import EmployeeProfile

class Command(BaseCommand):
    help = 'Resets the password for a Director account'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the director')
        parser.add_argument('new_password', type=str, help='The new password')

    def handle(self, *args, **options):
        username = options['username']
        new_password = options['new_password']

        try:
            user = User.objects.get(username=username)
            if not hasattr(user, 'profile') or user.profile.role != 'director':
                self.stdout.write(self.style.ERROR(f'User "{username}" is not a director.'))
                return

            user.set_password(new_password)
            user.profile.is_locked = False
            user.profile.failed_login_attempts = 0
            user.profile.save()
            user.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully reset password for director "{username}". Account unlocked.'))

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist.'))
