from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from students.models import UserProfile

class Command(BaseCommand):
    help = 'Creates default users'

    def handle(self, *args, **options):
        users = [
            ('director', 'director', 'المدير'),
            ('librarian', 'librarian', 'المكتبي'),
            ('storekeeper', 'storekeeper', 'المخزني'),
            ('archivist', 'archivist', 'الأرشيفي'),
            ('secretariat', 'secretariat', 'الأمانة'),
        ]

        for username, role, first_name in users:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password='123456', first_name=first_name)
                # Profile is created by signal, just update it
                # If signal didn't fire (sometimes happens in weird transaction states), create it
                if not hasattr(user, 'profile'):
                    UserProfile.objects.create(user=user, role=role)
                else:
                    profile = user.profile
                    profile.role = role
                    profile.save()
                self.stdout.write(self.style.SUCCESS(f'Created user {username}'))
            else:
                user = User.objects.get(username=username)
                if not hasattr(user, 'profile'):
                    UserProfile.objects.create(user=user, role=role)
                else:
                    profile = user.profile
                    profile.role = role
                    profile.save()
                self.stdout.write(self.style.WARNING(f'User {username} updated'))
