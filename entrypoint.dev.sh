#!/bin/sh
set -e

echo "Waiting for database..."
while ! python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; do
  sleep 1
done

echo "Initializing database (if needed)..."
python init_db.py

export FLASK_APP=wsgi:app
export FLASK_DEBUG="${FLASK_DEBUG:-1}"

echo "Starting Flask development server (hot reload)..."
exec flask run --host=0.0.0.0 --port=8000 --reload
