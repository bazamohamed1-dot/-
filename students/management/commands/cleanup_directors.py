from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from students.models import EmployeeProfile

class Command(BaseCommand):
    help = 'Enforce Single Director Policy: Keeps BAZA as director, removes others.'

    def handle(self, *args, **options):
        target_username = 'BAZA'

        try:
            baza_user = User.objects.get(username=target_username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{target_username}' not found. Aborting to avoid locking out all admins."))
            return

        # Ensure BAZA is director
        if not hasattr(baza_user, 'profile'):
            EmployeeProfile.objects.create(user=baza_user, role='director')
            self.stdout.write(self.style.SUCCESS(f"Created profile for '{target_username}' as Director."))
        else:
            if baza_user.profile.role != 'director':
                baza_user.profile.role = 'director'
                baza_user.profile.save()
                self.stdout.write(self.style.SUCCESS(f"Updated '{target_username}' role to Director."))

        # Find other directors
        other_directors = EmployeeProfile.objects.filter(role='director').exclude(user__username=target_username)

        count = other_directors.count()
        if count > 0:
            self.stdout.write(self.style.WARNING(f"Found {count} other directors. Deleting their accounts as requested..."))
            for profile in other_directors:
                user = profile.user
                username = user.username
                user.delete() # Deletes user and profile (due to cascade)
                self.stdout.write(f"Deleted user: {username}")
        else:
            self.stdout.write(self.style.SUCCESS("No other directors found."))

        self.stdout.write(self.style.SUCCESS(f"Single Director Policy Enforced. '{target_username}' is the only Director."))
