#!/bin/bash

# Video Analysis Agent - Build and Run Script
echo "🎬 Video Analysis Agent - Build and Run Script"
echo "=============================================="

# Set error handling
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found! Please run this script from video-analysis-agent directory."
    exit 1
fi

print_header "1. Cleaning up old containers and images"
docker-compose down --remove-orphans || true

print_header "2. Checking Docker environment"
docker --version
docker-compose --version

print_header "3. Creating required networks (if they don't exist)"
docker network create n8n-network 2>/dev/null || print_status "n8n-network already exists"
docker network create video-network 2>/dev/null || print_status "video-network already exists"

print_header "4. Building services"
print_status "Building Cutdown Generator..."
docker-compose build cutdown-generator

print_status "Building Revoice Service..."
docker-compose build revoice

print_status "Building Analyzer..."
docker-compose build analyzer

print_status "Building Whisper..."
docker-compose build whisper

# Storybook removed - no longer needed

print_header "5. Starting all services"
docker-compose up -d

print_header "6. Waiting for services to start..."
sleep 10

print_header "7. Checking service health"

# Check Cutdown Generator
print_status "Testing Cutdown Generator (Port 5679)..."
if curl -f -s http://localhost:5679/health > /dev/null; then
    print_status "✅ Cutdown Generator is healthy"
else
    print_warning "⚠️ Cutdown Generator not responding yet"
fi

# Check Revoice
print_status "Testing Revoice Service (Port 5680)..."
if curl -f -s http://localhost:5680/health > /dev/null; then
    print_status "✅ Revoice Service is healthy"
else
    print_warning "⚠️ Revoice Service not responding yet"
fi

# Check Analyzer
print_status "Testing Analyzer (Port 8000)..."
if curl -f -s http://localhost:8000/health > /dev/null; then
    print_status "✅ Analyzer is healthy"
else
    print_warning "⚠️ Analyzer not responding yet"
fi

print_header "8. Service Summary"
echo ""
echo "🌐 Services:"
echo "   📋 Cutdown Generator:  http://localhost:5679"
echo "   💋 Revoice Service:    http://localhost:5680"
echo "   🎬 Analyzer:           http://localhost:8000"
echo "   🎙️ Whisper:            http://localhost:9000"
echo "   📚 Storybook:          http://localhost:6006"
echo ""
echo "📁 Shared Volumes:"
echo "   📂 Videos:             $(pwd)/videos/"
echo "   📂 Temp:               $(pwd)/temp/"
echo "   📂 Models:             $(pwd)/models/"
echo ""
echo "🚀 Quick Test Commands:"
echo "   curl http://localhost:5679/health  # Cutdown Generator"
echo "   curl http://localhost:5680/health  # Revoice Service"
echo "   curl http://localhost:8000/health  # Analyzer"
echo "   curl -F \"video=@test.mp4\" http://localhost:5680/upload  # Revoice Upload"
echo "   curl -F \"video=@test.mp4\" http://localhost:5679/upload  # Cutdown Upload"
echo ""

print_header "9. Docker Container Status"
docker-compose ps

print_status "🎉 Video Analysis Agent is ready!"
print_status "Check logs with: docker-compose logs -f [service-name]"
print_status "Stop with: docker-compose down"

# Optional: Show recent logs
if [ "$1" = "--show-logs" ]; then
    print_header "Recent logs:"
    docker-compose logs --tail=20
fi

echo ""
echo "✅ Video Analysis Agent setup complete!" 