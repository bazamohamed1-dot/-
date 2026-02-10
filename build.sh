#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate

# Run image migration to fix memory issues (best effort)
python manage.py migrate_images || true
