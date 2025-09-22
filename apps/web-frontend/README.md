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
