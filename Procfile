web: gunicorn hotel_demo.wsgi --log-file - 
worker: celery -A your_project worker --loglevel=info
beat: celery -A hotel_demo beat --loglevel=info
