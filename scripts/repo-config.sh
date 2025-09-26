#!/bin/bash
# Repository Configuration for Splitting
# Update these values before running the split script

# GitHub Configuration
export ORG_NAME="your-github-org"  # Replace with your GitHub organization
export MONOREPO_URL="https://github.com/${ORG_NAME}/multi-ai-agent.git"  # Replace with your monorepo URL

# Repository Naming Convention
export REPO_PREFIX=""  # Optional prefix for all repositories
export REPO_SUFFIX=""  # Optional suffix for all repositories

# Data Plane Services
export DATA_PLANE_SERVICES=(
    "api-gateway:apps/data-plane/api-gateway"
    "model-gateway:apps/data-plane/model-gateway"
    "orchestrator:apps/data-plane/orchestrator"
    "router-service:apps/data-plane/router-service"
    "realtime-gateway:apps/data-plane/realtime-gateway"
    "ingestion-service:apps/data-plane/ingestion-service"
    "analytics-service:apps/data-plane/analytics-service"
    "retrieval-service:apps/data-plane/retrieval-service"
    "tools-service:apps/data-plane/tools-service"
    "memory-service:apps/data-plane/memory-service"
    "chat-adapters:apps/data-plane/chat-adapters"
    "semantic-cache-service:apps/data-plane/semantic-cache-service"
    "event-relay-service:apps/data-plane/event-relay-service"
    "migration-runner:apps/data-plane/migration-runner"
    "agents-service:apps/data-plane/agents-service"
    "eval-service:apps/data-plane/eval-service"
)

# Control Plane Services
export CONTROL_PLANE_SERVICES=(
    "config-service:apps/control-plane/config-service"
    "feature-flags-service:apps/control-plane/feature-flags-service"
    "registry-service:apps/control-plane/registry-service"
    "policy-adapter:apps/control-plane/policy-adapter"
    "usage-metering:apps/control-plane/usage-metering"
    "audit-log:apps/control-plane/audit-log"
    "notification-service:apps/control-plane/notification-service"
    "tenant-service:apps/control-plane/tenant-service"
    "capacity-monitor:apps/control-plane/capacity-monitor"
    "billing-service:apps/control-plane/billing-service"
)

# Meta Repository
export META_REPO_NAME="meta-repo"
