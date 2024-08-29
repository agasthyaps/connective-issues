FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p uploads temp

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run the application
CMD ["python", "run.py"]