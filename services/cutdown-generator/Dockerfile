# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables to ensure logs are sent straight to stdout
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 5679

# Define the command to run the application using gunicorn (tuned)
CMD ["gunicorn", "--bind", "0.0.0.0:5679", "--workers", "2", "--worker-class", "gthread", "--threads", "8", "--keep-alive", "15", "--timeout", "300", "--max-requests", "1000", "--max-requests-jitter", "100", "app:app"]
