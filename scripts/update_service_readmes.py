#!/usr/bin/env python3
"""
Update all service READMEs with observability sync instructions.
"""

import os
import re
from pathlib import Path

SERVICES = [
    "api-gateway", "analytics-service", "orchestrator", "router-service",
    "realtime", "ingestion", "billing-service", "tenant-service", 
    "chat-adapters", "tool-service", "eval-service", "capacity-monitor",
    "admin-portal", "web-frontend"
]

def get_observability_section():
    """Generate the observability section for service READMEs."""
    return """
## 📊 Observability & Monitoring

This service includes comprehensive observability configurations for production monitoring.

### Available Configurations

- **📈 Grafana Dashboard**: `observability/dashboards/{service}.json`
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
./platform/scripts/sync-observability.sh sync-service {service}

# Sync only dashboard
./platform/scripts/sync-observability.sh sync-dashboards

# Sync only alerts
./platform/scripts/sync-observability.sh sync-alerts

# Validate configuration
./platform/scripts/sync-observability.sh validate

# Dry run to see what would be changed
./platform/scripts/sync-observability.sh --dry-run sync-service {service}
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

- **📈 Dashboard**: [Grafana Dashboard](https://grafana.company.com/d/{service})
- **🔍 Logs**: [Loki Logs](https://grafana.company.com/explore?query={{service="{service}"}})
- **🔎 Traces**: [Jaeger UI](https://jaeger.company.com/search?service={service})
- **🚨 Alerts**: [AlertManager](https://alertmanager.company.com/#/alerts?filter={{service="{service}"}})

### Key Metrics to Monitor

```promql
# Request Rate
rate(http_requests_total{{service="{service}"}}[5m])

# Error Rate
rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]) / rate(http_requests_total{{service="{service}"}}[5m]) * 100

# Latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m]))

# CPU Usage
rate(container_cpu_usage_seconds_total{{container="{service}"}}[5m]) * 100

# Memory Usage
container_memory_usage_bytes{{container="{service}"}} / 1024/1024/1024
```

### Local Development Monitoring

For local development, you can run a lightweight monitoring stack:

```bash
# Start local monitoring stack
make dev-monitoring

# View local dashboard
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```"""

def update_readme(service_name):
    """Update README.md for a specific service."""
    readme_path = f"apps/{service_name}/README.md"
    
    if not os.path.exists(readme_path):
        print(f"❌ README.md not found for {service_name}")
        return False
    
    with open(readme_path, 'r') as f:
        content = f.read()
    
    # Generate observability section with service name
    obs_section = get_observability_section().replace("{service}", service_name)
    
    # Check if observability section already exists
    if "## 📊 Observability & Monitoring" in content:
        # Replace existing section
        pattern = r'## 📊 Observability & Monitoring.*?(?=\n## |\n# |\Z)'
        content = re.sub(pattern, obs_section.strip(), content, flags=re.DOTALL)
        print(f"✅ Updated existing observability section in {service_name}")
    else:
        # Add new section before the last section or at the end
        if "## Related Documentation" in content:
            content = content.replace("## Related Documentation", obs_section + "\n\n## Related Documentation")
        elif "## Contributing" in content:
            content = content.replace("## Contributing", obs_section + "\n\n## Contributing")
        elif "## License" in content:
            content = content.replace("## License", obs_section + "\n\n## License")
        else:
            # Add at the end
            content += obs_section
        print(f"✅ Added new observability section to {service_name}")
    
    # Write updated content
    with open(readme_path, 'w') as f:
        f.write(content)
    
    return True

def main():
    print("📚 Updating service READMEs with observability sync instructions...")
    
    updated_count = 0
    failed_count = 0
    
    for service in SERVICES:
        if update_readme(service):
            updated_count += 1
        else:
            failed_count += 1
    
    print(f"\n🎯 Summary:")
    print(f"   ✅ Updated: {updated_count} services")
    print(f"   ❌ Failed: {failed_count} services")
    
    if failed_count == 0:
        print(f"\n🎉 All service READMEs updated successfully!")
    
    print(f"\n📋 Added sections include:")
    print(f"   - Observability configurations overview")
    print(f"   - Sync script usage instructions") 
    print(f"   - Environment variables setup")
    print(f"   - Quick links to monitoring tools")
    print(f"   - Key PromQL metrics queries")
    print(f"   - Local development monitoring")

if __name__ == "__main__":
    main()
