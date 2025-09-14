# Test Topology

## 📋 **Overview**

This document defines the test topology for the Multi-AI-Agent platform, mapping which dependencies are mocked vs live for each test suite across the three execution modes (MOCK, GOLDEN, LIVE_SMOKE).

## 🎯 **Test Execution Modes**

### **MOCK Mode**
- **Purpose**: Fast unit tests with complete isolation
- **Speed**: < 30 seconds for full suite
- **Dependencies**: All external services mocked
- **Data**: In-memory synthetic data
- **Deterministic**: Yes (seed=42, temp=0.0)

### **GOLDEN Mode**
- **Purpose**: Deterministic integration tests with recorded responses
- **Speed**: < 5 minutes for full suite
- **Dependencies**: Ephemeral containers + recorded LLM responses
- **Data**: Production-like synthetic data
- **Deterministic**: Yes (seed=42, temp=0.0)

### **LIVE_SMOKE Mode**
- **Purpose**: Production-like validation with minimal traffic
- **Speed**: < 15 minutes for full suite
- **Dependencies**: Full stack with production-like configuration
- **Data**: Production-like dataset
- **Deterministic**: Mostly (seed=42, temp=0.1)

## 🏗️ **Test Topology Matrix**

### **Unit Tests**
```yaml
unit_tests:
  mode: MOCK
  dependencies:
    database: "mocked (SQLAlchemy in-memory)"
    redis: "mocked (fakeredis)"
    nats: "mocked (pytest-nats)"
    llm_services: "mocked (responses recorded)"
    external_apis: "mocked (httpx-mock)"
    vector_db: "mocked (in-memory vectors)"
  
  test_count: 400+
  execution_time: "< 30s"
  isolation: "complete"
```

### **Contract Tests**
```yaml
contract_tests:
  mode: MOCK
  dependencies:
    database: "mocked (schema validation only)"
    redis: "not used"
    nats: "not used"
    llm_services: "not used"
    external_apis: "mocked (schema validation)"
    vector_db: "not used"
  
  test_count: 150+
  execution_time: "< 60s"
  isolation: "schema-only"
```

### **Integration Tests**
```yaml
integration_tests:
  mode: GOLDEN
  dependencies:
    database: "ephemeral (PostgreSQL container)"
    redis: "ephemeral (Redis container)"
    nats: "ephemeral (NATS JetStream container)"
    llm_services: "mocked (cassette responses)"
    external_apis: "mocked (recorded responses)"
    vector_db: "ephemeral (Qdrant container)"
  
  test_count: 200+
  execution_time: "< 5min"
  isolation: "container-based"
```

### **E2E Tests**
```yaml
e2e_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (test database)"
    redis: "live (test instance)"
    nats: "live (test JetStream)"
    llm_services: "live (minimal calls)"
    external_apis: "mocked (test endpoints)"
    vector_db: "live (test collection)"
  
  test_count: 10 flows
  execution_time: "< 15min"
  isolation: "test-environment"
```

### **Realtime Tests**
```yaml
realtime_tests:
  mode: MOCK
  dependencies:
    database: "mocked (session state)"
    redis: "mocked (session storage)"
    nats: "mocked (message routing)"
    llm_services: "not used"
    external_apis: "not used"
    vector_db: "not used"
  
  test_count: 50+
  execution_time: "< 10min"
  isolation: "websocket-mocked"
```

### **Router Tests**
```yaml
router_tests:
  mode: GOLDEN
  dependencies:
    database: "ephemeral (router state)"
    redis: "ephemeral (feature cache)"
    nats: "ephemeral (decision events)"
    llm_services: "mocked (routing responses)"
    external_apis: "not used"
    vector_db: "not used"
  
  test_count: 100+
  execution_time: "< 10min"
  isolation: "ml-model-mocked"
```

### **RAG Tests**
```yaml
rag_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (document metadata)"
    redis: "live (embedding cache)"
    nats: "live (search events)"
    llm_services: "live (embedding generation)"
    external_apis: "not used"
    vector_db: "live (test collections)"
  
  test_count: 75+
  execution_time: "< 10min"
  isolation: "tenant-isolated"
```

### **Tools-Saga Tests**
```yaml
tools_saga_tests:
  mode: GOLDEN
  dependencies:
    database: "ephemeral (saga state)"
    redis: "ephemeral (idempotency)"
    nats: "ephemeral (compensation events)"
    llm_services: "mocked (tool responses)"
    external_apis: "mocked (tool endpoints)"
    vector_db: "not used"
  
  test_count: 60+
  execution_time: "< 15min"
  isolation: "saga-mocked"
```

### **Chaos Tests**
```yaml
chaos_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (with failure injection)"
    redis: "live (with failure injection)"
    nats: "live (with failure injection)"
    llm_services: "live (with timeout injection)"
    external_apis: "mocked (with failure injection)"
    vector_db: "live (with failure injection)"
  
  test_count: 25+
  execution_time: "< 20min"
  isolation: "failure-injected"
```

### **Performance Tests**
```yaml
performance_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (under load)"
    redis: "live (under load)"
    nats: "live (under load)"
    llm_services: "live (limited calls)"
    external_apis: "mocked (load generation)"
    vector_db: "live (under load)"
  
  test_count: 4 profiles
  execution_time: "< 30min"
  isolation: "load-tested"
```

### **Observability Tests**
```yaml
observability_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (metrics collection)"
    redis: "live (metrics collection)"
    nats: "live (metrics collection)"
    llm_services: "mocked (metrics generation)"
    external_apis: "not used"
    vector_db: "live (metrics collection)"
  
  test_count: 40+
  execution_time: "< 5min"
  isolation: "metrics-focused"
```

### **Adversarial Tests**
```yaml
adversarial_tests:
  mode: MOCK
  dependencies:
    database: "mocked (attack vectors)"
    redis: "mocked (attack vectors)"
    nats: "mocked (attack vectors)"
    llm_services: "mocked (injection attacks)"
    external_apis: "mocked (injection attacks)"
    vector_db: "mocked (injection attacks)"
  
  test_count: 80+
  execution_time: "< 10min"
  isolation: "attack-isolated"
```

### **Security Tests**
```yaml
security_tests:
  mode: LIVE_SMOKE
  dependencies:
    database: "live (with security validation)"
    redis: "live (with security validation)"
    nats: "live (with security validation)"
    llm_services: "live (with security validation)"
    external_apis: "mocked (security validation)"
    vector_db: "live (with security validation)"
  
  test_count: 120+
  execution_time: "< 10min"
  isolation: "security-validated"
```

## 🔧 **Dependency Mocking Details**

### **Database Mocking**
```python
# MOCK Mode - In-memory SQLAlchemy
@pytest.fixture(scope="function")
def mock_database():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()

# GOLDEN Mode - Ephemeral PostgreSQL
@pytest.fixture(scope="session")
def ephemeral_database():
    container = postgresql_container(
        image="postgres:15",
        environment={
            "POSTGRES_DB": "test_db",
            "POSTGRES_PASSWORD": "test_password"
        }
    )
    container.start()
    yield container.get_connection_url()
    container.stop()

# LIVE_SMOKE Mode - Test Database
@pytest.fixture(scope="session")
def test_database():
    return os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
```

### **Redis Mocking**
```python
# MOCK Mode - FakeRedis
@pytest.fixture(scope="function")
def mock_redis():
    redis = fakeredis.FakeRedis()
    yield redis
    redis.flushall()

# GOLDEN/LIVE_SMOKE Mode - Container Redis
@pytest.fixture(scope="session")
def redis_container():
    container = redis_container(
        image="redis:7",
        ports={"6379/tcp": None}
    )
    container.start()
    yield f"redis://localhost:{container.get_exposed_port(6379)}"
    container.stop()
```

### **NATS Mocking**
```python
# MOCK Mode - pytest-nats
@pytest.fixture(scope="function")
def mock_nats():
    with patch('nats.connect') as mock_connect:
        mock_nats = AsyncMock()
        mock_connect.return_value = mock_nats
        yield mock_nats

# GOLDEN/LIVE_SMOKE Mode - Container NATS
@pytest.fixture(scope="session")
def nats_container():
    container = nats_container(
        image="nats:2.9",
        ports={"4222/tcp": None, "8222/tcp": None}
    )
    container.start()
    yield f"nats://localhost:{container.get_exposed_port(4222)}"
    container.stop()
```

### **LLM Services Mocking**
```python
# MOCK Mode - Recorded Responses
@pytest.fixture(scope="function")
def mock_llm():
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = {
            "choices": [{"message": {"content": "Mocked response"}}]
        }
        yield mock_create

# GOLDEN Mode - Cassette Responses
@pytest.fixture(scope="function")
def golden_llm(cassette_dir):
    cassette_loader = LLMCassetteLoader(cassette_dir)
    with cassette_loader.use_cassette("test_name"):
        yield cassette_loader

# LIVE_SMOKE Mode - Limited Live Calls
@pytest.fixture(scope="function")
def live_llm():
    # Use real LLM with rate limiting and cost controls
    return LimitedLLMClient(
        max_calls_per_test=10,
        max_cost_per_test=0.01
    )
```

## 📊 **Test Isolation Strategy**

### **Container Isolation**
```yaml
container_isolation:
  strategy: "ephemeral_containers"
  cleanup: "automatic_after_test"
  networking: "isolated_networks"
  storage: "temporary_volumes"
  
  containers:
    - name: "postgres-test"
      image: "postgres:15"
      environment:
        POSTGRES_DB: "test_db"
        POSTGRES_PASSWORD: "test_password"
      ports:
        - "5432:5432"
    
    - name: "redis-test"
      image: "redis:7"
      ports:
        - "6379:6379"
    
    - name: "nats-test"
      image: "nats:2.9"
      ports:
        - "4222:4222"
        - "8222:8222"
    
    - name: "qdrant-test"
      image: "qdrant/qdrant:latest"
      ports:
        - "6333:6333"
```

### **Data Isolation**
```yaml
data_isolation:
  strategy: "tenant_namespacing"
  cleanup: "per_test_cleanup"
  privacy: "synthetic_data_only"
  
  synthetic_data:
    tenants: 10
    users_per_tenant: 5
    documents_per_tenant: 20
    conversations_per_user: 3
    messages_per_conversation: 5
  
  privacy_compliance:
    no_real_pii: true
    synthetic_generation: true
    data_retention: "7_days"
    audit_logging: true
```

### **Network Isolation**
```yaml
network_isolation:
  strategy: "docker_networks"
  dns: "internal_resolution"
  security: "no_external_access"
  
  networks:
    - name: "test-network"
      driver: "bridge"
      ipam:
        config:
          - subnet: "172.20.0.0/16"
  
  policies:
    - allow_internal_communication: true
    - block_external_access: true
    - enable_service_discovery: true
```

## 🚀 **Test Execution Strategy**

### **Parallel Execution**
```yaml
parallel_execution:
  strategy: "test_level_parallelization"
  max_workers: 4
  isolation: "per_worker_isolation"
  
  suites:
    unit_tests: "parallel"
    contract_tests: "parallel"
    integration_tests: "sequential"
    e2e_tests: "sequential"
    performance_tests: "sequential"
```

### **Test Selection**
```yaml
test_selection:
  strategy: "impact_based"
  fallback: "full_suite"
  
  rules:
    - changed_files: "apps/api-gateway/*"
      run_suites: ["unit_tests", "contract_tests", "integration_tests", "e2e_tests"]
    
    - changed_files: "apps/router-service/*"
      run_suites: ["unit_tests", "router_tests", "performance_tests"]
    
    - changed_files: "libs/contracts/*"
      run_suites: ["contract_tests", "integration_tests"]
```

---

**Status**: ✅ Production-Ready Test Topology  
**Last Updated**: September 2024  
**Version**: 1.0.0
