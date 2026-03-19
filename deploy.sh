#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if service is healthy
check_health() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Checking health of $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is healthy!"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
        ((attempt++))
    done
    
    print_error "$service_name failed to become healthy after $max_attempts attempts"
    return 1
}

# Function to run pre-deployment checks
pre_deployment_checks() {
    print_status "Running pre-deployment checks..."
    
    # Check if docker is installed
    if ! [ -x "$(command -v docker)" ]; then
        print_error "Docker is not installed."
        exit 1
    fi
    
    # Check if docker compose is available
    if ! [ -x "$(command -v docker compose)" ] && ! docker-compose version > /dev/null 2>&1; then
        print_error "Docker Compose is not available."
        exit 1
    fi
    
    # Check if required files exist
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found."
        exit 1
    fi
    
    print_success "Pre-deployment checks passed!"
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    
    # Frontend tests
    if [ -d "frontend" ]; then
        print_status "Running frontend tests..."
        cd frontend
        if CI=1 npm run test:coverage -- --run; then
            print_success "Frontend tests passed!"
        else
            print_warning "Frontend tests failed, but continuing deployment..."
        fi
        cd ..
    fi
    
    # Backend tests
    if [ -d "backend" ]; then
        print_status "Running backend tests..."
        cd backend
        
        # Check if Python is available
        if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
            print_warning "Python not found in PATH, skipping backend tests..."
        else
            # Use python3 if available, otherwise python
            PYTHON_CMD="python3"
            if ! command -v python3 &> /dev/null; then
                PYTHON_CMD="python"
            fi
            
            if $PYTHON_CMD manage.py test; then
                print_success "Backend tests passed!"
            else
                print_warning "Backend tests failed, but continuing deployment..."
            fi
        fi
        cd ..
    fi
}

# Function to build and deploy
build_and_deploy() {
    print_status "Building and deploying application..."
    
    # Stop existing containers
    print_status "Stopping existing containers..."
    docker compose down --remove-orphans || true
    
    # Build new images
    print_status "Building new images..."
    docker compose build --no-cache
    
    # Start containers
    print_status "Starting containers..."
    docker compose up -d
    
    # Wait for containers to be ready
    print_status "Waiting for containers to be ready..."
    sleep 10
}

# Function to run post-deployment setup
post_deployment_setup() {
    print_status "Running post-deployment setup..."
    
    # Wait for backend to be ready
    check_health "Backend" "http://localhost:8000/api/"
    
    # Determine Python command for Docker exec
    PYTHON_CMD="python3"
    if ! docker compose exec -T backend python3 --version &> /dev/null; then
        PYTHON_CMD="python"
    fi
    
    # Run migrations
    print_status "Running database migrations..."
    docker compose exec -T backend $PYTHON_CMD manage.py makemigrations solutions core || true
    docker compose exec -T backend $PYTHON_CMD manage.py migrate
    
    # Seed data
    print_status "Seeding database..."
    docker compose exec -T backend $PYTHON_CMD seed.py || true
    
    print_success "Post-deployment setup completed!"
}

# Function to display deployment summary
deployment_summary() {
    print_success "Deployment completed successfully!"
    echo ""
    echo "🌐 Application URLs:"
    echo "   Frontend: http://localhost:8089"
    echo "   Backend API: http://localhost:8000"
    echo "   Database: localhost:5432"
    echo ""
    echo "📊 Container Status:"
    docker compose ps
    echo ""
    echo "🔍 Health Check:"
    check_health "Frontend" "http://localhost:8089"
    check_health "Backend" "http://localhost:8000/api/"
}

# Main deployment flow
main() {
    print_status "Starting deployment of Private GTO Wizard..."
    echo ""
    
    # Run pre-deployment checks
    pre_deployment_checks
    echo ""
    
    # Run tests (optional - can be skipped with --skip-tests flag)
    if [ "$1" != "--skip-tests" ]; then
        run_tests
        echo ""
    fi
    
    # Build and deploy
    build_and_deploy
    echo ""
    
    # Post-deployment setup
    post_deployment_setup
    echo ""
    
    # Show summary
    deployment_summary
}

# Handle script arguments
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [--skip-tests]"
    echo ""
    echo "Options:"
    echo "  --skip-tests    Skip running tests before deployment"
    echo "  --help, -h      Show this help message"
    exit 0
fi

# Run main function with all arguments
main "$@"
