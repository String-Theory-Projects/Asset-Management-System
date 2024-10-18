#!/bin/bash

# Start Gunicorn with logging
gunicorn hotel_demo.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --log-file=- \
    --access-logfile=- \
    --error-logfile=- \
    --capture-output &

# Start Celery worker as appuser
celery -A hotel_demo worker --uid=appuser --gid=appuser --loglevel=info &

# Start Celery beat (if you're using periodic tasks) as appuser
celery -A hotel_demo beat --uid=appuser --gid=appuser --loglevel=info &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?