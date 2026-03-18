#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting deployment of Private GTO Wizard..."

# Check if docker is installed
if ! [ -x "$(command -v docker)" ]; then
  echo 'Error: docker is not installed.' >&2
  exit 1
fi

# Build and start containers
echo "📦 Building images and starting containers..."
docker-compose up --build -d

echo "✅ Deployment complete!"
echo "🌐 Frontend: http://localhost"
echo "⚙️  Backend API: http://localhost:8000"
echo "📊 Database: localhost:5432"

# Show container status
docker-compose ps
