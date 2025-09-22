.PHONY: help deploy clean

ENV ?= dev
IMAGE_TAG ?= latest
NAMESPACE ?= multi-ai-agent-$(ENV)

help:
	@echo "API Gateway Deployment - Available Commands:"
	@echo ""
	@echo "  deploy       Deploy to environment (ENV=dev|staging|prod)"
	@echo "  clean        Clean deployment"
	@echo ""
	@echo "Usage: make deploy ENV=dev IMAGE_TAG=v1.0.0"

deploy:
	@echo "Deploying API Gateway to $(ENV) environment..."
	kustomize build overlays/$(ENV) | \
		sed 's|IMAGE_TAG|$(IMAGE_TAG)|g' | \
		kubectl apply -f -
	kubectl rollout status deployment/api-gateway -n $(NAMESPACE)

clean:
	kustomize build overlays/$(ENV) | kubectl delete -f - || true
