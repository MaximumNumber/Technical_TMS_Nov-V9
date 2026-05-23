#!/bin/bash
set -e

echo "=== TMS Django Server Starting ==="

export PATH="/home/runner/.local/bin:/home/runner/workspace/.pythonlibs/bin:$PATH"
export PYTHONPATH="/home/runner/workspace"

cd /home/runner/workspace

echo "Running migrations..."
python manage.py migrate --noinput 2>&1

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>&1

echo "Seeding system admin (if needed)..."
python manage.py seed_admin --username admin --password admin123 2>&1 || true

echo "Creating cache directory..."
mkdir -p /tmp/django_tms_cache

echo "=== Starting Gunicorn on port 5000 ==="
exec gunicorn tms.wsgi:application \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --threads 2 \
    --timeout 60 \
    --keep-alive 5 \
    --log-level warning \
    --access-logfile -
