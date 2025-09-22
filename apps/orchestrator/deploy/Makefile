.PHONY: help deploy clean validate

ENV ?= dev
IMAGE_TAG ?= latest
NAMESPACE ?= multi-ai-agent-$(ENV)

help:
	@echo "Orchestrator Deployment - Available Commands:"
	@echo ""
	@echo "  deploy       Deploy to environment (ENV=dev|staging|prod)"
	@echo "  clean        Clean deployment"
	@echo "  validate     Validate manifests"
	@echo ""
	@echo "Usage: make deploy ENV=dev IMAGE_TAG=v1.0.0"

deploy:
	@echo "Deploying orchestrator to $(ENV) environment..."
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@kustomize build overlays/$(ENV) | \
		sed 's|IMAGE_TAG|$(IMAGE_TAG)|g' | \
		kubectl apply -f -
	@kubectl rollout status deployment/orchestrator -n $(NAMESPACE) --timeout=300s

clean:
	@echo "Cleaning orchestrator from $(ENV) environment..."
	@kustomize build overlays/$(ENV) | kubectl delete -f - || true

validate:
	@echo "Validating orchestrator manifests..."
	@kustomize build overlays/dev | kubectl apply --dry-run=client -f -
	@kustomize build overlays/staging | kubectl apply --dry-run=client -f -
	@kustomize build overlays/prod | kubectl apply --dry-run=client -f -
	@echo "✓ All manifests are valid"