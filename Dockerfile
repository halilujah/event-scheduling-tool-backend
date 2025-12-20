FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run with gunicorn using eventlet workers
# -w 1 = single worker (required for SQLite + WebSocket)
# -k eventlet = use eventlet worker for Socket.IO support
# -b 0.0.0.0:8080 = bind to all interfaces on port 8080
# --timeout 120 = allow up to 120 seconds for requests
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:8080", "--timeout", "120", "main:app"]
