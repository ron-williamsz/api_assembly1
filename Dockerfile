FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p uploads processed

ARG PORT=5358
EXPOSE ${PORT}

CMD gunicorn --bind 0.0.0.0:${PORT:-5358} --workers ${WORKERS:-4} --timeout 120 app:app
