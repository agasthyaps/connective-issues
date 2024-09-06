FROM python:3.9-slim

WORKDIR /app

# Install system dependencies, including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y ffmpeg

COPY . .

# Create necessary directories
RUN mkdir -p uploads temp static

EXPOSE 8080

ENV PORT 8080

CMD exec python run.py