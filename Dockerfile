# Dockerfile for the Python Web App

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Make port available to the world outside this container
EXPOSE $PORT

# Define environment variable
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Run the startup script
CMD ["./start.sh"]
