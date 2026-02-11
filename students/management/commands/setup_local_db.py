from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
import os

class Command(BaseCommand):
    help = 'Sets up the local SQLite database and imports data from backup'

    def handle(self, *args, **options):
        self.stdout.write("🛠️  Setting up Local Database...")

        # 1. Migrate
        self.stdout.write("   Running Migrations...")
        call_command('migrate')

        # 2. Load Data
        backup_file = 'local_data.json'
        if os.path.exists(backup_file):
            self.stdout.write(f"   📥 Loading data from {backup_file}...")
            try:
                call_command('loaddata', backup_file)
                self.stdout.write(self.style.SUCCESS("   ✅ Data Loaded Successfully!"))
            except Exception as e:
                 self.stdout.write(self.style.ERROR(f"   ❌ Error loading data: {e}"))
        else:
            self.stdout.write(self.style.WARNING(f"   ⚠️  {backup_file} not found. Skipping data import."))

        self.stdout.write(self.style.SUCCESS("🎉 Local Setup Complete!"))
        self.stdout.write("   You can now run the server with: python manage.py runserver 0.0.0.0:8000")
