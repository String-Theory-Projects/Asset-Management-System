# Use the official Python image from the Docker Hub
FROM python:3.8

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Mosquitto
RUN apt-get update && apt-get install -y mosquitto

# Copy the Django project files into the container
COPY . /app/

# Copy Mosquitto configuration
COPY mosquitto.conf /etc/mosquitto/mosquitto.conf

# Expose ports for Django and Mosquitto
EXPOSE 8000 1883 8883

# Create a startup script
RUN echo '#!/bin/bash\n\
service mosquitto start\n\
gunicorn hotel_demo.wsgi:application --bind 0.0.0.0:8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Start both Mosquitto and Django
CMD ["/app/start.sh"]