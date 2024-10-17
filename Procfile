web: gunicorn hotel_demo.wsgi --log-file=- --access-logfile=- --error-logfile=- --capture-output
worker: celery -A hotel_demo worker --loglevel=info
beat: celery -A hotel_demo beat --loglevel=info
