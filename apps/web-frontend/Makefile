.PHONY: help dev test lint build run clean type-check

# Default target
help:
	@echo "Web Frontend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          Install dependencies for development"
	@echo "  test         Run all tests"
	@echo "  lint         Run linting and formatting checks"
	@echo "  type-check   Run TypeScript type checking"
	@echo "  run          Run the development server"
	@echo ""
	@echo "Build & Deploy:"
	@echo "  build        Build for production"
	@echo "  clean        Clean build artifacts"

# Install dependencies
dev:
	npm install

# Run tests
test:
	npm run test

# Linting and formatting
lint:
	npm run lint

# Type checking
type-check:
	npm run type-check

# Run development server
run:
	npm run dev

# Build for production
build:
	npm run build

# Clean artifacts
clean:
	rm -rf dist/ node_modules/ .vite/
