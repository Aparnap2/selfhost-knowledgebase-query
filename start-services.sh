#!/bin/bash

# Start services with proper timing and debugging
echo "Starting NotebookLM services..."

# Create required directories if they don't exist
mkdir -p ./data
mkdir -p ./python-executor/plots
mkdir -p ./python-executor/sessions
mkdir -p ./python-executor/tmp
mkdir -p ./backend/cache
mkdir -p ./backend/cache/search
mkdir -p ./backend/logs

# Stop any existing containers (except Ollama)
echo "Stopping any existing containers..."
docker-compose down

# Remove any unhealthy containers (except Ollama)
echo "Removing any unhealthy containers..."
docker ps -a | grep unhealthy | grep -v ollama | awk '{print $1}' | xargs -r docker rm -f

# Check if Ollama is running
OLLAMA_RUNNING=$(docker ps | grep ollama | wc -l)
if [ "$OLLAMA_RUNNING" -eq 0 ]; then
  echo "WARNING: Ollama container is not running. Please start it first with:"
  echo "docker run -d --name ollama -p 11434:11434 -v ollama_data:/root/.ollama ollama/ollama"
  echo "Continuing anyway, but the application may not work properly..."
fi

# Connect Ollama to our network if it exists
if [ "$OLLAMA_RUNNING" -ne 0 ]; then
  echo "Connecting Ollama to our network..."
  docker network connect booklm_network ollama 2>/dev/null || true
fi

# Pull latest images
echo "Pulling latest images..."
docker-compose pull

# Start Chroma first
echo "Starting Chroma database..."
docker-compose up -d chroma
echo "Waiting for Chroma to be healthy..."
sleep 15

# Check if Chroma is healthy
CHROMA_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' chroma 2>/dev/null || echo "container not found")
if [ "$CHROMA_HEALTHY" != "healthy" ]; then
  echo "Waiting longer for Chroma to be healthy..."
  sleep 30
  CHROMA_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' chroma 2>/dev/null || echo "container not found")
  if [ "$CHROMA_HEALTHY" != "healthy" ]; then
    echo "Chroma is not healthy. Please check the logs with 'docker logs chroma'"
    docker logs chroma
    echo "Continuing anyway, but the application may not work properly..."
  fi
fi

# Start backend
echo "Starting backend service..."
docker-compose up -d backend
echo "Waiting for backend to be healthy..."
sleep 15

# Start Python executor
echo "Starting Python executor service..."
docker-compose up -d python-executor
echo "Waiting for Python executor to be healthy..."
sleep 10

# Start frontend
echo "Starting frontend service..."
docker-compose up -d frontend
echo "Waiting for frontend to be healthy..."
sleep 10

# Show status of all containers
echo "All services started. Container status:"
docker-compose ps

echo "You can access the application at http://localhost:5173"
echo "To view logs, use: docker-compose logs -f"
echo "To stop all services, use: docker-compose down"
echo ""
echo "NOTE: This application is using your existing Ollama container."
echo "If you encounter issues with Ollama connectivity, try:"
echo "docker network connect booklm_network ollama"