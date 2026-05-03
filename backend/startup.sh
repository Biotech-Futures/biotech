#!/bin/bash

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start ASGI server
echo "Starting Daphne ASGI server..."
daphne -b 0.0.0.0 -p 8000 config.asgi:application
