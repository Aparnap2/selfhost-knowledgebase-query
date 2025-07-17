FROM python:3.11-slim

WORKDIR /app

# Install Node.js and npm
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Node.js dependencies
COPY package.json ./
RUN npm install --no-package-lock

COPY . .

# Add a health check script
COPY healthcheck.py .

# Set the Chroma server host and port
ENV CHROMA_HOST=chroma
ENV CHROMA_PORT=8000

# Expose the port for the Node.js server
EXPOSE 3001

# Start the Node.js server
CMD ["node", "server.js"]
