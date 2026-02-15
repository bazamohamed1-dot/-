#!/bin/sh

# Wait for database
echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"

# Apply database migrations
python manage.py migrate
python manage.py migrate_images || true

# Collect static files
python manage.py collectstatic --noinput

# Start server
exec "$@"
