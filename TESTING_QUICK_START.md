# 🧪 Quick Testing Guide

## 🚀 Start Testing in 5 Minutes

### 1. Start All Services

```bash
# Start complete environment
./scripts/start-local.sh

# Wait for services to be ready (script will show progress)
```

### 2. Run Basic Tests

```bash
# Quick health check
./scripts/test-health.sh

# Test API endpoints
./scripts/test-api.sh

# Test frontend applications
./scripts/test-frontend.sh
```

### 3. Run Complete Test Suite

```bash
# Run all tests with detailed reporting
./scripts/run-all-tests.sh

# View HTML report
open test-results/report_*.html
```

## 🔍 Individual Test Scripts

| Script                | Purpose                | Time |
| --------------------- | ---------------------- | ---- |
| `test-health.sh`      | Service health checks  | 30s  |
| `test-api.sh`         | API endpoint testing   | 1m   |
| `test-frontend.sh`    | Frontend accessibility | 30s  |
| `test-e2e.sh`         | End-to-end user flow   | 2m   |
| `test-performance.sh` | Response time testing  | 1m   |
| `test-database.sh`    | Database connectivity  | 30s  |
| `test-security.sh`    | Security scanning      | 3m   |
| `test-load.sh`        | Load testing with k6   | 3m   |

## 🌐 Service URLs

| Service              | URL                   | Description            |
| -------------------- | --------------------- | ---------------------- |
| **🤖 AI Chatbot**    | http://localhost:3001 | Main chatbot interface |
| **🌍 Web Frontend**  | http://localhost:3000 | Web application        |
| **👨‍💼 Admin Portal**  | http://localhost:8099 | Admin dashboard        |
| **🔌 API Gateway**   | http://localhost:8000 | Backend API            |
| **🧠 Model Gateway** | http://localhost:8080 | AI model service       |

## 🔧 Common Commands

```bash
# Check service status
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs -f

# Restart services
docker-compose -f docker-compose.local.yml restart

# Stop all services
docker-compose -f docker-compose.local.yml down
```

## 🆘 Troubleshooting

### Services not starting?

```bash
# Check logs
docker-compose -f docker-compose.local.yml logs

# Restart everything
./scripts/start-local.sh
```

### Tests failing?

```bash
# Check health first
./scripts/test-health.sh

# Check specific service
docker-compose -f docker-compose.local.yml logs <service-name>
```

### Performance issues?

```bash
# Check resource usage
docker stats

# Run performance test
./scripts/test-performance.sh
```

## 📊 Test Results

Test results are saved in:

- `test-results/test_*.log` - Detailed logs
- `test-results/summary_*.txt` - Test summary
- `test-results/report_*.html` - HTML report

## 🎯 Testing Checklist

- [ ] All services running
- [ ] Health checks pass
- [ ] API endpoints respond
- [ ] Frontend applications load
- [ ] End-to-end flow works
- [ ] Performance is acceptable
- [ ] No security vulnerabilities
- [ ] Database connectivity works

## 🚀 Quick Commands

```bash
# Start and test everything
./scripts/start-local.sh && ./scripts/run-all-tests.sh

# Just test what's running
./scripts/run-all-tests.sh

# Continuous testing (if fswatch installed)
./scripts/continuous-test.sh
```

For detailed instructions, see [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)
