# Shared Contracts Makefile
.DEFAULT_GOAL := help

# Variables
OPENAPI_GENERATOR_VERSION := 7.0.1
BUF_VERSION := 1.28.1

.PHONY: help install-tools generate-all clean lint validate

help: ## Show this help message
	@echo "🎯 Shared Platform Contracts"
	@echo "=============================="
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-tools: ## Install required code generation tools
	@echo "📦 Installing code generation tools..."
	@command -v openapi-generator-cli >/dev/null 2>&1 || npm install -g @openapitools/openapi-generator-cli@$(OPENAPI_GENERATOR_VERSION)
	@command -v orval >/dev/null 2>&1 || npm install -g orval
	@command -v buf >/dev/null 2>&1 || (echo "Please install buf: https://docs.buf.build/installation" && exit 1)
	@echo "✅ All tools installed"

validate: ## Validate shared contracts
	@echo "🔍 Validating shared contracts..."
	@echo "Validating OpenAPI spec..."
	@openapi-generator-cli validate -i shared.yaml
	@echo "Validating Protocol Buffer files..."
	@buf lint
	@echo "✅ All contracts are valid"

generate-go-shared: ## Generate Go clients for shared contracts
	@echo "🔧 Generating Go shared clients..."
	@mkdir -p gen/go
	@openapi-generator-cli generate \
		-i shared.yaml \
		-g go \
		-o gen/go/shared \
		--package-name shared \
		--git-user-id company \
		--git-repo-id multi-ai-agent \
		--additional-properties=moduleName=github.com/company/multi-ai-agent/contracts/gen/go/shared
	@buf generate --template buf.gen.yaml
	@echo "✅ Go shared clients generated"

generate-python-shared: ## Generate Python clients for shared contracts
	@echo "🔧 Generating Python shared clients..."
	@mkdir -p gen/python
	@openapi-generator-cli generate \
		-i shared.yaml \
		-g python \
		-o gen/python/shared \
		--package-name shared_contracts \
		--additional-properties=projectName=shared-contracts,packageVersion=1.0.0
	@buf generate --template buf.gen.yaml
	@echo "✅ Python shared clients generated"

generate-typescript-shared: ## Generate TypeScript clients for shared contracts
	@echo "🔧 Generating TypeScript shared clients..."
	@mkdir -p gen/typescript
	@openapi-generator-cli generate \
		-i shared.yaml \
		-g typescript-axios \
		-o gen/typescript/shared \
		--additional-properties=npmName=@company/shared-contracts,npmVersion=1.0.0,supportsES6=true
	@buf generate --template buf.gen.yaml
	@echo "✅ TypeScript shared clients generated"

generate-all: generate-go-shared generate-python-shared generate-typescript-shared ## Generate all shared clients
	@echo "🎉 All shared clients generated successfully!"

lint: ## Lint all contract files
	@echo "🔍 Linting contracts..."
	@echo "Linting Protocol Buffer files..."
	@buf lint
	@echo "✅ All contracts pass linting"

clean: ## Clean generated files
	@echo "🧹 Cleaning generated files..."
	@rm -rf gen/
	@echo "✅ Generated files cleaned"

breaking: ## Check for breaking changes
	@echo "🔍 Checking for breaking changes..."
	@buf breaking --against '.git#branch=main'
	@echo "✅ No breaking changes detected"

# Development helpers
watch: ## Watch for changes and regenerate
	@echo "👀 Watching for changes..."
	@while true; do \
		inotifywait -e modify,create,delete shared.yaml shared.proto 2>/dev/null && \
		make generate-all; \
	done
