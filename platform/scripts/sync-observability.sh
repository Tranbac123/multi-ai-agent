#!/bin/bash
set -euo pipefail

# ==============================================================================
# Platform Observability Sync Script
# 
# This script syncs service-specific observability configurations to the
# monitoring stack (Grafana, Prometheus, AlertManager).
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
GRAFANA_URL="${GRAFANA_URL:-http://grafana.company.com}"
GRAFANA_API_KEY="${GRAFANA_API_KEY:-}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.company.com}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://alertmanager.company.com}"
DRY_RUN="${DRY_RUN:-false}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Platform Observability Sync Script

USAGE:
    $0 [OPTIONS] [COMMAND] [SERVICE]

COMMANDS:
    sync-all        Sync all observability configurations
    sync-dashboards Sync Grafana dashboards only
    sync-alerts     Sync AlertManager rules only  
    sync-service    Sync configurations for specific service
    validate        Validate all configurations
    list-services   List all available services

OPTIONS:
    -h, --help      Show this help message
    -d, --dry-run   Show what would be done without making changes
    -e, --env       Environment (production, staging, development)
    -v, --verbose   Verbose output

EXAMPLES:
    # Sync all configurations
    $0 sync-all

    # Sync specific service
    $0 sync-service api-gateway

    # Dry run to see what would be changed
    $0 --dry-run sync-all

    # Sync only dashboards
    $0 sync-dashboards

ENVIRONMENT VARIABLES:
    GRAFANA_URL         Grafana base URL
    GRAFANA_API_KEY     Grafana API key for authentication
    PROMETHEUS_URL      Prometheus base URL
    ALERTMANAGER_URL    AlertManager base URL
    DRY_RUN            Set to 'true' for dry run mode
    ENVIRONMENT        Target environment

EOF
}

# Validate prerequisites
validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    # Check required tools
    local missing_tools=()
    
    if ! command -v curl >/dev/null 2>&1; then
        missing_tools+=("curl")
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        missing_tools+=("jq")
    fi
    
    if ! command -v yq >/dev/null 2>&1; then
        log_warning "yq not found - YAML processing will be limited"
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install missing tools and try again"
        exit 1
    fi
    
    # Validate environment variables
    if [[ -z "$GRAFANA_API_KEY" && "$DRY_RUN" != "true" ]]; then
        log_error "GRAFANA_API_KEY is required for non-dry-run mode"
        log_error "Set GRAFANA_API_KEY environment variable or use --dry-run"
        exit 1
    fi
    
    log_success "Prerequisites validated"
}

# Discover services
discover_services() {
    local services=()
    
    for service_dir in "$PROJECT_ROOT/apps"/*; do
        if [[ -d "$service_dir/observability" ]]; then
            services+=($(basename "$service_dir"))
        fi
    done
    
    echo "${services[@]}"
}

# Validate service observability configuration
validate_service_config() {
    local service="$1"
    local service_dir="$PROJECT_ROOT/apps/$service"
    local obs_dir="$service_dir/observability"
    local valid=true
    
    log_info "Validating $service configuration..."
    
    # Check required files exist
    local required_files=(
        "$obs_dir/alerts.yaml"
        "$obs_dir/SLO.md"
        "$obs_dir/runbook.md"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Missing required file: $file"
            valid=false
        fi
    done
    
    # Check dashboard directory
    if [[ ! -d "$obs_dir/dashboards" ]]; then
        log_error "Missing dashboards directory: $obs_dir/dashboards"
        valid=false
    fi
    
    # Validate dashboard JSON
    for dashboard in "$obs_dir/dashboards"/*.json; do
        if [[ -f "$dashboard" ]]; then
            if ! jq empty "$dashboard" 2>/dev/null; then
                log_error "Invalid JSON in dashboard: $dashboard"
                valid=false
            fi
        fi
    done
    
    # Validate alerts YAML
    if [[ -f "$obs_dir/alerts.yaml" ]]; then
        if command -v yq >/dev/null 2>&1; then
            if ! yq eval . "$obs_dir/alerts.yaml" >/dev/null 2>&1; then
                log_error "Invalid YAML in alerts: $obs_dir/alerts.yaml"
                valid=false
            fi
        fi
    fi
    
    if [[ "$valid" == "true" ]]; then
        log_success "$service configuration is valid"
    else
        log_error "$service configuration has errors"
    fi
    
    echo "$valid"
}

# Sync Grafana dashboard
sync_dashboard() {
    local service="$1"
    local dashboard_file="$PROJECT_ROOT/apps/$service/observability/dashboards/$service.json"
    
    if [[ ! -f "$dashboard_file" ]]; then
        log_warning "Dashboard not found for $service: $dashboard_file"
        return 1
    fi
    
    log_info "Syncing dashboard for $service..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would sync dashboard: $dashboard_file"
        return 0
    fi
    
    # Create or update dashboard via Grafana API
    local response
    response=$(curl -s -X POST \
        -H "Authorization: Bearer $GRAFANA_API_KEY" \
        -H "Content-Type: application/json" \
        -d @"$dashboard_file" \
        "$GRAFANA_URL/api/dashboards/db" \
        -w "%{http_code}")
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        log_success "Dashboard synced for $service"
    else
        log_error "Failed to sync dashboard for $service (HTTP $http_code)"
        log_error "Response: $body"
        return 1
    fi
}

# Sync AlertManager rules
sync_alerts() {
    local service="$1"
    local alerts_file="$PROJECT_ROOT/apps/$service/observability/alerts.yaml"
    
    if [[ ! -f "$alerts_file" ]]; then
        log_warning "Alerts not found for $service: $alerts_file"
        return 1
    fi
    
    log_info "Syncing alerts for $service..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would sync alerts: $alerts_file"
        return 0
    fi
    
    # For AlertManager, we typically reload configuration files
    # This is a placeholder - actual implementation depends on your setup
    
    # Option 1: If using Prometheus Operator, update PrometheusRule CRD
    if command -v kubectl >/dev/null 2>&1; then
        local rule_name="$service-alerts"
        kubectl create configmap "$rule_name" \
            --from-file="$alerts_file" \
            --namespace="$ENVIRONMENT" \
            --dry-run=client -o yaml | \
            kubectl apply -f -
        
        if [[ $? -eq 0 ]]; then
            log_success "Alerts synced for $service"
        else
            log_error "Failed to sync alerts for $service"
            return 1
        fi
    else
        # Option 2: Copy to AlertManager config directory and reload
        log_warning "kubectl not available - alerts sync skipped for $service"
        log_info "Manually copy $alerts_file to AlertManager and reload"
    fi
}

# Sync single service
sync_service() {
    local service="$1"
    
    log_info "Syncing observability for $service..."
    
    # Validate configuration first
    if [[ "$(validate_service_config "$service")" != "true" ]]; then
        log_error "Configuration validation failed for $service"
        return 1
    fi
    
    # Sync dashboard
    sync_dashboard "$service" || log_warning "Dashboard sync failed for $service"
    
    # Sync alerts  
    sync_alerts "$service" || log_warning "Alerts sync failed for $service"
    
    log_success "Observability sync completed for $service"
}

# Sync all services
sync_all() {
    log_info "Starting observability sync for all services..."
    
    local services
    IFS=' ' read -ra services <<< "$(discover_services)"
    
    log_info "Found ${#services[@]} services: ${services[*]}"
    
    local failed_services=()
    
    for service in "${services[@]}"; do
        if ! sync_service "$service"; then
            failed_services+=("$service")
        fi
    done
    
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        log_success "All services synced successfully"
    else
        log_error "Failed to sync ${#failed_services[@]} services: ${failed_services[*]}"
        return 1
    fi
}

# Sync only dashboards
sync_all_dashboards() {
    log_info "Syncing all dashboards..."
    
    local services
    IFS=' ' read -ra services <<< "$(discover_services)"
    
    local failed_services=()
    
    for service in "${services[@]}"; do
        if ! sync_dashboard "$service"; then
            failed_services+=("$service")
        fi
    done
    
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        log_success "All dashboards synced successfully"
    else
        log_error "Failed to sync dashboards for: ${failed_services[*]}"
        return 1
    fi
}

# Sync only alerts
sync_all_alerts() {
    log_info "Syncing all alerts..."
    
    local services
    IFS=' ' read -ra services <<< "$(discover_services)"
    
    local failed_services=()
    
    for service in "${services[@]}"; do
        if ! sync_alerts "$service"; then
            failed_services+=("$service")
        fi
    done
    
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        log_success "All alerts synced successfully"
    else
        log_error "Failed to sync alerts for: ${failed_services[*]}"
        return 1
    fi
}

# Validate all configurations
validate_all() {
    log_info "Validating all service configurations..."
    
    local services
    IFS=' ' read -ra services <<< "$(discover_services)"
    
    local invalid_services=()
    
    for service in "${services[@]}"; do
        if [[ "$(validate_service_config "$service")" != "true" ]]; then
            invalid_services+=("$service")
        fi
    done
    
    if [[ ${#invalid_services[@]} -eq 0 ]]; then
        log_success "All configurations are valid"
    else
        log_error "Invalid configurations found in: ${invalid_services[*]}"
        return 1
    fi
}

# List available services
list_services() {
    local services
    IFS=' ' read -ra services <<< "$(discover_services)"
    
    log_info "Available services with observability configurations:"
    for service in "${services[@]}"; do
        echo "  - $service"
    done
    
    echo ""
    log_info "Total: ${#services[@]} services"
}

# Main function
main() {
    local command=""
    local service=""
    local verbose=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            sync-all|sync-dashboards|sync-alerts|validate|list-services)
                command="$1"
                shift
                ;;
            sync-service)
                command="$1"
                service="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Set verbose mode
    if [[ "$verbose" == "true" ]]; then
        set -x
    fi
    
    # Show configuration
    log_info "Configuration:"
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Dry Run: $DRY_RUN"
    log_info "  Grafana URL: $GRAFANA_URL"
    log_info "  Prometheus URL: $PROMETHEUS_URL"
    log_info "  AlertManager URL: $ALERTMANAGER_URL"
    echo ""
    
    # Validate prerequisites
    validate_prerequisites
    
    # Execute command
    case $command in
        sync-all)
            sync_all
            ;;
        sync-dashboards)
            sync_all_dashboards
            ;;
        sync-alerts)
            sync_all_alerts
            ;;
        sync-service)
            if [[ -z "$service" ]]; then
                log_error "Service name required for sync-service command"
                exit 1
            fi
            sync_service "$service"
            ;;
        validate)
            validate_all
            ;;
        list-services)
            list_services
            ;;
        "")
            log_error "No command specified"
            show_help
            exit 1
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
