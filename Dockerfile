FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p uploads temp

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app