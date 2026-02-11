import os
import sys
import django
from django.core.management import call_command
import json
import requests
from urllib.parse import urlparse
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

def migrate_data():
    print("🚀 Starting Cloud to Local Migration...")

    # Step 1: Export Data from Cloud DB
    print("1️⃣  Exporting data from Cloud Database...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings_cloud')
    django.setup()

    output_file = 'cloud_dump.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        call_command('dumpdata', exclude=['auth.permission', 'contenttypes'], stdout=f)

    print(f"✅ Data exported to {output_file}")

    # Step 2: Download Media Files
    print("2️⃣  Downloading Media Files (Photos)...")
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    media_dir = BASE_DIR / 'media'
    students_dir = media_dir / 'students_photos'
    school_logo_dir = media_dir / 'school_logo'

    students_dir.mkdir(parents=True, exist_ok=True)
    school_logo_dir.mkdir(parents=True, exist_ok=True)

    updated_data = []

    for item in data:
        # Handle Student Photos
        if item['model'] == 'students.student':
            photo_url = item['fields'].get('photo_path')
            if photo_url and photo_url.startswith('http'):
                filename = f"student_{item['pk']}.jpg"
                filepath = students_dir / filename

                try:
                    print(f"   ⬇️  Downloading {filename}...")
                    r = requests.get(photo_url)
                    if r.status_code == 200:
                        with open(filepath, 'wb') as img_file:
                            img_file.write(r.content)
                        # Update path to local relative path
                        item['fields']['photo_path'] = f"students_photos/{filename}"
                    else:
                        print(f"   ⚠️  Failed to download {photo_url}")
                except Exception as e:
                    print(f"   ❌ Error downloading {photo_url}: {e}")

        # Handle School Logo
        if item['model'] == 'students.schoolsettings':
            logo_url = item['fields'].get('logo')
            if logo_url and logo_url.startswith('http'):
                filename = "logo.png"
                filepath = school_logo_dir / filename

                try:
                    print(f"   ⬇️  Downloading Logo...")
                    r = requests.get(logo_url)
                    if r.status_code == 200:
                        with open(filepath, 'wb') as img_file:
                            img_file.write(r.content)
                        item['fields']['logo'] = f"school_logo/{filename}"
                except Exception as e:
                    print(f"   ❌ Error downloading logo: {e}")

        updated_data.append(item)

    local_dump_file = 'local_data.json'
    with open(local_dump_file, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Processed data saved to {local_dump_file}")

    # Step 3: Switch to Local Settings and Import
    print("3️⃣  Importing data into Local SQLite Database...")

    # We need to reload Django with new settings.
    # Since we can't easily unload modules, we'll suggest the user run the import command.
    print("\n⚠️  MIGRATION STEP 1 COMPLETE.")
    print(f"   File created: {local_dump_file}")
    print("   Now run the following commands to finish:")
    print("   ---------------------------------------")
    print("   python manage.py migrate")
    print(f"   python manage.py loaddata {local_dump_file}")
    print("   ---------------------------------------")

if __name__ == '__main__':
    migrate_data()
