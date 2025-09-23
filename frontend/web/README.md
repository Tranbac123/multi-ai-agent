# Web Frontend

React-based user interface for the Multi-AI-Agent platform.

## Technology Stack

- React 18
- TypeScript
- Vite
- TailwindCSS

## Quick Start

```bash
# Install dependencies
make dev

# Run tests
make test

# Start development server
make run
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API URL | http://localhost:8000 |
| `VITE_WS_URL` | WebSocket URL | ws://localhost:8004 |

## Development

```bash
# Run development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test

# Lint code
npm run lint
```

## Deployment

```bash
# Deploy to development
cd deploy && make deploy ENV=dev

# Deploy to production
cd deploy && make deploy ENV=prod
```

## Features

- Multi-tenant dashboard
- Real-time chat interface
- Analytics and reporting
- User management
- Subscription management

## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/web-frontend.json`
  - Request rate, latency percentiles, error rate
  - Resource usage (CPU, memory)
  - Service-specific metrics

- **🚨 Alert Rules**: `observability/alerts.yaml`
  - High error rate (>5%)
  - High latency (P95 threshold)
  - Service down detection
  - Resource exhaustion warnings

- **🎯 Service Level Objectives**: `observability/SLO.md`
  - Availability, latency, and error rate targets
  - Error budget tracking
  - PromQL queries for SLI monitoring

- **📖 Runbook**: `observability/runbook.md`
  - Troubleshooting procedures
  - Common issues and solutions
  - Escalation procedures

### Sync to Monitoring Stack

To deploy observability configurations to your monitoring stack:

```bash
# Sync all configurations for this service
./platform/scripts/sync-observability.sh sync-service web-frontend

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service web-frontend
```

### Environment Variables for Sync

```bash
export GRAFANA_URL="https://grafana.your-company.com"
export GRAFANA_API_KEY="your-grafana-api-key"
export PROMETHEUS_URL="https://prometheus.your-company.com"
export ALERTMANAGER_URL="https://alertmanager.your-company.com"
export ENVIRONMENT="production"  # or staging, development
```

### Quick Links (Production)

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/web-frontend)
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="web-frontend"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service=web-frontend)
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="web-frontend"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="web-frontend"}}[5m])

# Error Rate
rate(http_requests_total{{service="web-frontend",status=~"5.."}}[5m]) / rate(http_requests_total{{service="web-frontend"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="web-frontend"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="web-frontend"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="web-frontend"}} / 1024/1024/1024
```

### Local Development Monitoring

For local development, you can run a lightweight monitoring stack:

```bash
# Start local monitoring stack
make dev-monitoring

# View local dashboard
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```