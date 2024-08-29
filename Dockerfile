FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better cache utilization
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p uploads temp static

# Create a non-root user
RUN useradd -m myuser
RUN chown -R myuser:myuser /app
USER myuser

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Set the PORT environment variable
ENV PORT 8080

# Run the application
CMD exec python run.py