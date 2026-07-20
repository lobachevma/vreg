#!/bin/sh
set -e

echo "Waiting for database..."
while ! python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; do
  sleep 1
done

echo "Starting application..."
python init_db.py
exec gunicorn --bind 0.0.0.0:8000 --workers 2 wsgi:app
