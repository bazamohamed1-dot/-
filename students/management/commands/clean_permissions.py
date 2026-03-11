import json
import ast
from django.core.management.base import BaseCommand
from students.models import EmployeeProfile

class Command(BaseCommand):
    help = 'Cleans up stringified lists in the permissions JSONField.'

    def handle(self, *args, **options):
        profiles = EmployeeProfile.objects.all()
        updated_count = 0
        for profile in profiles:
            if isinstance(profile.permissions, str):
                cleaned = None
                try:
                    perms_list = json.loads(profile.permissions.replace("'", '"'))
                    if isinstance(perms_list, list):
                        cleaned = perms_list
                except Exception:
                    pass

                if cleaned is None:
                    try:
                        perms_list = ast.literal_eval(profile.permissions)
                        if isinstance(perms_list, list):
                            cleaned = perms_list
                    except Exception:
                        pass

                if cleaned is None and "," in profile.permissions:
                    cleaned = [p.strip() for p in profile.permissions.split(',')]

                if cleaned is not None:
                    profile.permissions = cleaned
                    profile.save()
                    updated_count += 1
                else:
                    # Single permission string or malformed
                    if profile.permissions.strip():
                        profile.permissions = [profile.permissions.strip()]
                        profile.save()
                        updated_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully cleaned permissions for {updated_count} profiles.'))
