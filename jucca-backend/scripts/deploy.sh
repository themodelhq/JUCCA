#!/bin/bash

# ============================================
# JUCCA Infrastructure Deployment Script
# ============================================
# This script handles deployment of JUCCA to production
# Supports: Local, Docker, Cloud (AWS, GCP, Azure)
# ============================================

set -e  # Exit on error

# Configuration
PROJECT_NAME="jucca"
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKEND_DIR}/.env"
LOG_FILE="${BACKEND_DIR}/deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# Helper Functions
# ============================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    local deps=("docker" "docker-compose" "git")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        exit 1
    fi
    
    log_info "All dependencies satisfied"
}

load_env() {
    log_info "Loading environment variables..."
    
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
        log_info "Environment loaded from $ENV_FILE"
    else
        log_warn "No .env file found, using defaults"
    fi
}

# ============================================
# Database Operations
# ============================================

init_database() {
    log_info "Initializing database..."
    
    cd "$BACKEND_DIR"
    
    if [ -f "scripts/init_db.py" ]; then
        python scripts/init_db.py
        log_info "Database initialized"
    else
        log_warn "Database initialization script not found"
    fi
}

backup_database() {
    local backup_dir="${1:-./backups}"
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${backup_dir}/jucca_backup_${timestamp}.db"
    
    log_info "Creating database backup..."
    
    mkdir -p "$backup_dir"
    
    if [ -f "jucca.db" ]; then
        cp jucca.db "$backup_file"
        gzip "$backup_file"
        log_info "Backup created: ${backup_file}.gz"
    else
        log_warn "No database file found to backup"
    fi
}

# ============================================
# Docker Operations
# ============================================

docker_build() {
    log_info "Building Docker image..."
    
    cd "$BACKEND_DIR"
    docker build -t "${PROJECT_NAME}-backend:latest" .
    log_info "Docker image built successfully"
}

docker_run() {
    log_info "Starting JUCCA containers..."
    
    cd "$BACKEND_DIR"
    docker-compose up -d
    
    log_info "JUCCA is starting..."
    sleep 5
    
    # Health check
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            log_info "JUCCA is healthy and running"
            return 0
        fi
        log_info "Waiting for JUCCA to start... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    log_error "JUCCA failed to start within timeout"
    return 1
}

docker_stop() {
    log_info "Stopping JUCCA containers..."
    
    cd "$BACKEND_DIR"
    docker-compose down
    
    log_info "JUCCA containers stopped"
}

docker_restart() {
    docker_stop
    docker_run
}

docker_logs() {
    local service="${1:-backend}"
    local lines="${2:-100}"
    
    cd "$BACKEND_DIR"
    docker-compose logs -f --tail="$lines" "$service"
}

# ============================================
# Model Management
# ============================================

download_model() {
    local model_name="${1:-mistral-7b-openorca.gguf}"
    local model_dir="${BACKEND_DIR}/models"
    
    log_info "Downloading GPT4All model: $model_name"
    
    mkdir -p "$model_dir"
    
    # Check available disk space (need at least 10GB)
    local available=$(df -BG "$model_dir" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available" -lt 10 ]; then
        log_error "Insufficient disk space. Need at least 10GB, have ${available}GB"
        exit 1
    fi
    
    # Download model
    local model_url="https://gpt4all.io/models/gguf/${model_name}"
    
    log_info "Downloading from: $model_url"
    
    wget --progress=bar:force \
         -O "${model_dir}/${model_name}" \
         "$model_url"
    
    log_info "Model downloaded to ${model_dir}/${model_name}"
    
    # Verify file
    if [ -f "${model_dir}/${model_name}" ]; then
        local size=$(du -h "${model_dir}/${model_name}" | cut -f1)
        log_info "Model file size: $size"
    else
        log_error "Model download failed"
        exit 1
    fi
}

list_models() {
    local model_dir="${BACKEND_DIR}/models"
    
    echo "Available models in ${model_dir}:"
    if [ -d "$model_dir" ]; then
        ls -lh "$model_dir"/*.gguf 2>/dev/null || echo "  No models found"
    else
        echo "  Models directory not found"
    fi
}

# ============================================
# Monitoring
# ============================================

check_health() {
    log_info "Checking JUCCA health..."
    
    local endpoints=(
        "http://localhost:8000/health"
        "http://localhost:8000/docs"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local status=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint")
        if [ "$status" -eq 200 ]; then
            log_info "$endpoint - OK ($status)"
        else
            log_warn "$endpoint - $status"
        fi
    done
}

view_metrics() {
    log_info "Viewing metrics endpoints..."
    
    local endpoints=(
        "http://localhost:8000/metrics"
        "http://localhost:9090"
        "http://localhost:3000"
    )
    
    for endpoint in "${endpoints[@]}"; do
        echo "Endpoint: $endpoint"
        curl -s "$endpoint" 2>/dev/null | head -20 || echo "  (not available)"
        echo ""
    done
}

# ============================================
# Testing
# ============================================

run_tests() {
    log_info "Running tests..."
    
    cd "$BACKEND_DIR"
    
    if command -v pytest &> /dev/null; then
        pytest -v --tb=short tests/ || log_warn "Some tests failed"
    else
        log_warn "pytest not installed, skipping tests"
    fi
}

run_load_test() {
    local users="${1:-50}"
    local spawn_rate="${2:-5}"
    local runtime="${3:-60}"
    
    log_info "Running load test with $users users..."
    
    cd "$BACKEND_DIR/load_testing"
    
    # Start locust
    locust -f locustfile.py \
           --users "$users" \
           --spawn-rate "$spawn_rate" \
           --run-time "${runtime}s" \
           --headless \
           --host=http://localhost:8000 \
           --html=load_test_results.html
    
    log_info "Load test completed. Results saved to load_test_results.html"
}

# ============================================
# Deployment
# ============================================

deploy_local() {
    log_info "Deploying JUCCA locally..."
    
    check_dependencies
    load_env
    docker_build
    docker_run
    check_health
    log_info "Local deployment complete"
}

deploy_production() {
    log_info "Deploying JUCCA to production..."
    
    check_dependencies
    load_env
    
    # Database backup
    backup_database ./backups/$(date +%Y%m%d)
    
    # Build and deploy
    docker_build
    docker_stop
    docker_run
    
    # Run health checks
    check_health
    
    log_info "Production deployment complete"
}

# ============================================
# Cleanup
# ============================================

cleanup() {
    log_info "Cleaning up..."
    
    cd "$BACKEND_DIR"
    docker-compose down -v
    docker system prune -af
    
    log_info "Cleanup complete"
}

# ============================================
# Main
# ============================================

show_help() {
    echo "JUCCA Deployment Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  deploy-local       Deploy locally"
    echo "  deploy-prod       Deploy to production"
    echo "  start             Start containers"
    echo "  stop              Stop containers"
    echo "  restart           Restart containers"
    echo "  logs [service]    View logs"
    echo "  build             Build Docker image"
    echo "  init-db           Initialize database"
    echo "  backup            Backup database"
    echo "  download-model    Download GPT4All model"
    echo "  list-models       List downloaded models"
    echo "  health            Check health"
    echo "  metrics           View metrics endpoints"
    echo "  test              Run unit tests"
    echo "  load-test         Run load test"
    echo "  cleanup           Clean up containers and images"
    echo ""
}

# Main entry point
case "${1:-}" in
    deploy-local)
        deploy_local
        ;;
    deploy-prod|deploy-production)
        deploy_production
        ;;
    start)
        load_env
        docker_run
        ;;
    stop)
        docker_stop
        ;;
    restart)
        docker_restart
        ;;
    logs)
        docker_logs "${2:-backend}" "${3:-100}"
        ;;
    build)
        check_dependencies
        docker_build
        ;;
    init-db)
        init_database
        ;;
    backup)
        backup_database "${2:-./backups}"
        ;;
    download-model)
        download_model "${2:-mistral-7b-openorca.gguf}"
        ;;
    list-models)
        list_models
        ;;
    health)
        check_health
        ;;
    metrics)
        view_metrics
        ;;
    test)
        run_tests
        ;;
    load-test)
        run_load_test "${2:-50}" "${3:-5}" "${4:-60}"
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
