# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r celery && useradd -r -g celery celery -u 1000

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /app/

# Change ownership of the app directory to the non-root user
RUN chown -R celery:celery /app

# Switch to non-root user
USER celery

# Run Celery worker with explicit UID and GID
CMD ["celery", "-A", "hotel_demo", "worker", "--uid=1000", "--gid=1000", "--loglevel=info"]