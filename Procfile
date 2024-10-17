web: gunicorn hotel_demo.wsgi --log-file - 
worker: celery -A hotel_demo worker --loglevel=info
worker: celery -A hotel-demo worker --loglevel=info
beat: celery -A hotel_demo beat --loglevel=info
