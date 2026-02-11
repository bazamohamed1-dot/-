# Use the official Python 3.12 image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Create a non-root user (required by Hugging Face)
RUN useradd -m -u 1000 user

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code
COPY --chown=user:user . /app/

# Switch to the non-root user
USER user

# Collect static files
RUN python manage.py collectstatic --no-input

# Expose the Hugging Face port
EXPOSE 7860

# Start the application
CMD ["gunicorn", "School_Management.wsgi:application", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "2", "--timeout", "120"]
