#!/bin/bash

# Debug script for NotebookLM services
echo "NotebookLM Debug Tool"
echo "====================="

# Check Docker status
echo "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
  echo "ERROR: Docker is not running or not accessible. Please start Docker and try again."
  exit 1
else
  echo "Docker is running."
  echo "Docker version: $(docker --version)"
  echo "Docker containers running: $(docker ps -q | wc -l)"
fi

# Check container status
echo -e "\nContainer Status:"
echo "------------------"
docker-compose ps

# Check network connectivity
echo -e "\nNetwork Connectivity:"
echo "--------------------"
echo "Checking if containers can reach each other..."

# Check if Chroma is reachable
echo "Testing connection to Chroma..."
docker exec -it notebooklm_backend curl -s -o /dev/null -w "%{http_code}" http://chroma:8000/api/v1/heartbeat || echo "Failed to connect to Chroma"

# Check if backend is reachable
echo "Testing connection to Backend..."
docker exec -it notebooklm_frontend curl -s -o /dev/null -w "%{http_code}" http://backend:8000/health || echo "Failed to connect to Backend"

# Check logs for errors
echo -e "\nChecking logs for errors:"
echo "------------------------"

echo "Chroma logs (last 10 lines):"
docker logs chroma --tail 10 2>&1 | grep -i "error\|exception\|fail" || echo "No obvious errors found"

echo "Backend logs (last 10 lines):"
docker logs notebooklm_backend --tail 10 2>&1 | grep -i "error\|exception\|fail" || echo "No obvious errors found"

echo "Frontend logs (last 10 lines):"
docker logs notebooklm_frontend --tail 10 2>&1 | grep -i "error\|exception\|fail" || echo "No obvious errors found"

echo "Python executor logs (last 10 lines):"
docker logs notebooklm_python_executor --tail 10 2>&1 | grep -i "error\|exception\|fail" || echo "No obvious errors found"

# Check disk space
echo -e "\nDisk Space:"
echo "-----------"
df -h | grep -E "Filesystem|/dev/sda"

# Check memory usage
echo -e "\nMemory Usage:"
echo "-------------"
free -h

# Provide troubleshooting tips
echo -e "\nTroubleshooting Tips:"
echo "---------------------"
echo "1. If containers are unhealthy, try restarting them: docker-compose restart <service-name>"
echo "2. To view detailed logs: docker-compose logs -f <service-name>"
echo "3. To rebuild a service: docker-compose build <service-name>"
echo "4. To restart all services with proper timing: ./start-services.sh"
echo "5. To completely reset: docker-compose down -v && docker-compose up -d"