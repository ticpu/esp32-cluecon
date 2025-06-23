FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./
COPY test/ ./test/

# Copy configs
COPY sample_config.json ./
# Copy config.json if it exists (using glob pattern that won't fail if missing)
COPY config.jso[n] ./ 

# Create directories
RUN mkdir -p certs examples sandbox

# Copy examples
COPY examples/ ./examples/

# Config and certs should be mounted, not baked in
VOLUME ["/app/config.json", "/app/certs"]

# Expose port
EXPOSE 8080

# Run the gateway
CMD ["python3", "gateway_service.py"]