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

# Copy the Django project files into the container
COPY . /app/

# Expose port 8000 for the Django application
EXPOSE 8000

# Start the Django application with Gunicorn
CMD ["gunicorn", "hotel_demo.wsgi:application", "--bind", "0.0.0.0:8000"]
