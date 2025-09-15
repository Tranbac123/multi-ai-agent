# Fixtures and Test Data Management

## 📊 **Overview**

This document defines the test data management strategy for the Multi-AI-Agent platform, covering synthetic data generation, fixture management, and data privacy compliance.

## 🎯 **Test Data Strategy**

### **Three Execution Modes**

#### **MOCK Mode**

- **Purpose**: Fast unit tests with mocked dependencies
- **Data**: In-memory synthetic data
- **Dependencies**: None (all mocked)
- **Setup Time**: <5 seconds
- **Cleanup**: Automatic

#### **GOLDEN Mode**

- **Purpose**: Deterministic integration tests
- **Data**: Recorded LLM responses and known outputs
- **Dependencies**: Ephemeral containers
- **Setup Time**: <30 seconds
- **Cleanup**: Automatic

#### **LIVE_SMOKE Mode**

- **Purpose**: Production-like validation
- **Data**: Production-like dataset
- **Dependencies**: Full stack
- **Setup Time**: <5 minutes
- **Cleanup**: Automatic

## 🏗️ **Test Fixtures Architecture**

### **Fixture Hierarchy**

```python
# Base fixture for all tests
@pytest.fixture(scope="session")
def test_config():
    """Global test configuration."""
    return TestConfig.from_env()

# Environment-specific fixtures
@pytest.fixture(scope="session")
def mock_environment(test_config):
    """Mock environment setup."""
    if test_config.mode == TestMode.MOCK:
        return MockEnvironment()
    return None

@pytest.fixture(scope="session")
def golden_environment(test_config):
    """Golden environment setup."""
    if test_config.mode == TestMode.GOLDEN:
        return GoldenEnvironment()
    return None

@pytest.fixture(scope="session")
def live_environment(test_config):
    """Live environment setup."""
    if test_config.mode == TestMode.LIVE_SMOKE:
        return LiveEnvironment()
    return None
```

### **Entity Factories**

```python
class EntityFactory:
    """Factory for creating test entities with realistic data."""

    def __init__(self, seed: int = 42):
        """Initialize factory with deterministic seed."""
        random.seed(seed)
        self._tenant_counter = 0
        self._user_counter = 0
        self._document_counter = 0
        self._cart_counter = 0
        self._payment_counter = 0
        self._router_request_counter = 0
        self._websocket_session_counter = 0
        self._workflow_execution_counter = 0

    def create_tenant(self, tier: TenantTier = TenantTier.STANDARD) -> Tenant:
        """Create a test tenant."""
        self._tenant_counter += 1
        return Tenant(
            tenant_id=f"tenant_{self._tenant_counter:04d}",
            name=f"Test Tenant {self._tenant_counter}",
            tier=tier,
            config={
                "max_users": 100,
                "max_requests_per_month": 10000,
                "features": ["chat", "workflows", "analytics"]
            },
            created_at=datetime.now(),
            status=TenantStatus.ACTIVE
        )

    def create_user(self, tenant_id: str) -> User:
        """Create a test user."""
        self._user_counter += 1
        return User(
            user_id=f"user_{self._user_counter:04d}",
            tenant_id=tenant_id,
            email=f"user{self._user_counter}@example.com",
            name=f"Test User {self._user_counter}",
            role=UserRole.USER,
            created_at=datetime.now(),
            last_login=datetime.now()
        )

    def create_document(self, tenant_id: str) -> Document:
        """Create a test document."""
        self._document_counter += 1
        return Document(
            document_id=f"doc_{self._document_counter:04d}",
            tenant_id=tenant_id,
            title=f"Test Document {self._document_counter}",
            content=f"This is test document content {self._document_counter}.",
            document_type=DocumentType.KNOWLEDGE_BASE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
```

## 📝 **LLM Cassette Management**

### **Cassette Recording**

```python
class LLMCassetteRecorder:
    """Records and replays LLM interactions for deterministic testing."""

    def __init__(self, cassette_dir: str, test_mode: TestMode):
        self.cassette_dir = Path(cassette_dir)
        self.test_mode = test_mode
        self.recordings = {}

    def record_interaction(self, prompt: str, response: str, **kwargs) -> str:
        """Record LLM interaction."""
        if self.test_mode != TestMode.GOLDEN:
            return response

        # Normalize prompt for consistent recording
        normalized_prompt = self.normalize_prompt(prompt, **kwargs)

        # Generate cassette key
        cassette_key = self._generate_cassette_key(normalized_prompt)

        # Record interaction
        self.recordings[cassette_key] = {
            "prompt": normalized_prompt,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "metadata": kwargs
        }

        # Save to file
        self._save_cassette(cassette_key, self.recordings[cassette_key])

        return response

    def replay_interaction(self, prompt: str, **kwargs) -> str:
        """Replay recorded LLM interaction."""
        if self.test_mode != TestMode.GOLDEN:
            raise ValueError("Replay only available in GOLDEN mode")

        # Normalize prompt
        normalized_prompt = self.normalize_prompt(prompt, **kwargs)

        # Generate cassette key
        cassette_key = self._generate_cassette_key(normalized_prompt)

        # Load cassette
        cassette = self._load_cassette(cassette_key)

        if cassette is None:
            raise ValueError(f"No cassette found for key: {cassette_key}")

        return cassette["response"]

    def normalize_prompt(self, prompt: str, **kwargs) -> str:
        """Normalize prompt for consistent recording."""
        normalized = prompt

        # Remove timestamps
        timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
        normalized = re.sub(timestamp_pattern, '[TIMESTAMP]', normalized)

        # Remove UUIDs
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        normalized = re.sub(uuid_pattern, '[UUID]', normalized)

        # Remove dynamic IDs
        id_pattern = r'\b(id|ID|Id)\s*:\s*[a-zA-Z0-9_-]+'
        normalized = re.sub(id_pattern, r'\1: [ID]', normalized)

        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized.strip())

        return normalized
```

### **Golden Output Management**

```python
class GoldenOutputLoader:
    """Manages golden outputs for deterministic testing."""

    def __init__(self, golden_dir: str):
        self.golden_dir = Path(golden_dir)
        self.golden_outputs = {}

    def load_golden_output(self, test_name: str, output_key: str) -> Any:
        """Load golden output for comparison."""
        golden_file = self.golden_dir / f"{test_name}_{output_key}.json"

        if golden_file.exists():
            with open(golden_file, 'r') as f:
                return json.load(f)

        return None

    def save_golden_output(self, test_name: str, output_key: str, output: Any):
        """Save golden output for future comparison."""
        golden_file = self.golden_dir / f"{test_name}_{output_key}.json"

        # Normalize output
        normalized_output = self.normalize_output(output)

        with open(golden_file, 'w') as f:
            json.dump(normalized_output, f, indent=2, default=str)

    def compare_with_golden(self, test_name: str, output_key: str, actual_output: Any) -> bool:
        """Compare actual output with golden output."""
        golden_output = self.load_golden_output(test_name, output_key)

        if golden_output is None:
            # Save as new golden output
            self.save_golden_output(test_name, output_key, actual_output)
            return True

        # Normalize both outputs
        normalized_actual = self.normalize_output(actual_output)
        normalized_golden = self.normalize_output(golden_output)

        return normalized_actual == normalized_golden

    def normalize_output(self, output: Any) -> Any:
        """Normalize output for consistent comparison."""
        if isinstance(output, str):
            # Normalize whitespace
            normalized = re.sub(r'\s+', ' ', output.strip())

            # Remove timestamps
            timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
            normalized = re.sub(timestamp_pattern, '[TIMESTAMP]', normalized)

            # Remove UUIDs
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            normalized = re.sub(uuid_pattern, '[UUID]', normalized)

            return normalized

        elif isinstance(output, dict):
            return {k: self.normalize_output(v) for k, v in output.items()}

        elif isinstance(output, list):
            return [self.normalize_output(item) for item in output]

        else:
            return output
```

## 🔒 **Synthetic Data Generation**

### **Data Privacy Compliance**

```python
class SyntheticDataGenerator:
    """Generates synthetic test data that complies with privacy regulations."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def generate_synthetic_email(self) -> str:
        """Generate synthetic email address."""
        domains = ["example.com", "test.org", "demo.net"]
        names = ["john", "jane", "bob", "alice", "charlie", "diana"]

        name = random.choice(names)
        number = random.randint(100, 999)
        domain = random.choice(domains)

        return f"{name}{number}@{domain}"

    def generate_synthetic_phone(self) -> str:
        """Generate synthetic phone number."""
        area_code = random.randint(200, 999)
        exchange = random.randint(200, 999)
        number = random.randint(1000, 9999)

        return f"{area_code}-{exchange}-{number}"

    def generate_synthetic_name(self) -> str:
        """Generate synthetic name."""
        first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]

        first_name = random.choice(first_names)
        last_name = random.choice(last_names)

        return f"{first_name} {last_name}"

    def generate_synthetic_address(self) -> dict:
        """Generate synthetic address."""
        streets = ["Main St", "Oak Ave", "Pine Rd", "Cedar Blvd", "Maple Dr"]
        cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
        states = ["NY", "CA", "IL", "TX", "AZ"]

        street_number = random.randint(100, 9999)
        street_name = random.choice(streets)
        city = random.choice(cities)
        state = random.choice(states)
        zip_code = random.randint(10000, 99999)

        return {
            "street": f"{street_number} {street_name}",
            "city": city,
            "state": state,
            "zip": str(zip_code),
            "country": "US"
        }
```

### **Realistic Data Generation**

```python
class RealisticDataGenerator:
    """Generates realistic test data for comprehensive testing."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def generate_conversation_history(self, message_count: int = 10) -> List[dict]:
        """Generate realistic conversation history."""
        messages = []

        for i in range(message_count):
            if i % 2 == 0:  # User messages
                message = {
                    "role": "user",
                    "content": self._generate_user_message(),
                    "timestamp": datetime.now() - timedelta(minutes=message_count-i)
                }
            else:  # Assistant messages
                message = {
                    "role": "assistant",
                    "content": self._generate_assistant_message(),
                    "timestamp": datetime.now() - timedelta(minutes=message_count-i)
                }

            messages.append(message)

        return messages

    def _generate_user_message(self) -> str:
        """Generate realistic user message."""
        message_templates = [
            "I need help with {topic}",
            "Can you explain {topic}?",
            "How do I {action}?",
            "What is {topic}?",
            "I'm having trouble with {topic}",
            "Can you help me {action}?"
        ]

        topics = ["my account", "billing", "my order", "password reset", "product information"]
        actions = ["reset my password", "cancel my order", "update my profile", "contact support"]

        template = random.choice(message_templates)

        if "{topic}" in template:
            topic = random.choice(topics)
            return template.format(topic=topic)
        elif "{action}" in template:
            action = random.choice(actions)
            return template.format(action=action)

        return template

    def _generate_assistant_message(self) -> str:
        """Generate realistic assistant message."""
        response_templates = [
            "I'd be happy to help you with {topic}.",
            "Let me assist you with {topic}.",
            "I can help you {action}.",
            "Here's how to {action}:",
            "For {topic}, you can:"
        ]

        topics = ["your account", "billing", "your order", "password reset", "product information"]
        actions = ["reset your password", "cancel your order", "update your profile", "contact support"]

        template = random.choice(response_templates)

        if "{topic}" in template:
            topic = random.choice(topics)
            return template.format(topic=topic)
        elif "{action}" in template:
            action = random.choice(actions)
            return template.format(action=action)

        return template
```

## 🧹 **Test Data Cleanup**

### **Automatic Cleanup**

```python
class TestDataManager:
    """Manages test data lifecycle and cleanup."""

    def __init__(self):
        self.tracked_entities = []
        self.cleanup_hooks = []

    def track_entity(self, entity_type: str, entity_id: str, cleanup_func: Callable):
        """Track entity for cleanup."""
        self.tracked_entities.append({
            "type": entity_type,
            "id": entity_id,
            "cleanup_func": cleanup_func,
            "created_at": datetime.now()
        })

    def cleanup_entities(self):
        """Clean up all tracked entities."""
        for entity in self.tracked_entities:
            try:
                entity["cleanup_func"](entity["id"])
            except Exception as e:
                logger.warning(f"Failed to cleanup entity {entity['id']}: {e}")

        self.tracked_entities.clear()

    def clear_tracking(self):
        """Clear tracking without cleanup."""
        self.tracked_entities.clear()

    def register_cleanup_hook(self, hook_func: Callable):
        """Register cleanup hook."""
        self.cleanup_hooks.append(hook_func)

    def execute_cleanup_hooks(self):
        """Execute all cleanup hooks."""
        for hook in self.cleanup_hooks:
            try:
                hook()
            except Exception as e:
                logger.warning(f"Cleanup hook failed: {e}")
```

### **Fixture Cleanup**

```python
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatic test data cleanup after each test."""
    yield
    test_data_manager.cleanup_entities()

@pytest.fixture(scope="session", autouse=True)
def cleanup_session_data():
    """Session-level cleanup."""
    yield
    test_data_manager.execute_cleanup_hooks()
```

## 📊 **Test Data Statistics**

### **Data Volume Requirements**

```yaml
test_data_requirements:
  mock_mode:
    tenants: 10
    users_per_tenant: 5
    documents_per_tenant: 20
    conversations_per_user: 3
    messages_per_conversation: 5

  golden_mode:
    tenants: 50
    users_per_tenant: 10
    documents_per_tenant: 100
    conversations_per_user: 10
    messages_per_conversation: 10

  live_smoke_mode:
    tenants: 100
    users_per_tenant: 20
    documents_per_tenant: 500
    conversations_per_user: 20
    messages_per_conversation: 15
```

### **Performance Benchmarks**

```yaml
performance_benchmarks:
  data_generation:
    synthetic_user: "< 1ms"
    synthetic_conversation: "< 5ms"
    synthetic_document: "< 10ms"

  fixture_setup:
    mock_environment: "< 5s"
    golden_environment: "< 30s"
    live_environment: "< 5min"

  cleanup:
    mock_cleanup: "< 1s"
    golden_cleanup: "< 5s"
    live_cleanup: "< 30s"
```

## 🔄 **Data Refresh Strategy**

### **Cassette Refresh Policy**

```python
class CassetteRefreshPolicy:
    """Manages cassette refresh and validation."""

    def __init__(self, refresh_interval_days: int = 30):
        self.refresh_interval_days = refresh_interval_days

    def should_refresh_cassette(self, cassette_file: Path) -> bool:
        """Check if cassette should be refreshed."""
        if not cassette_file.exists():
            return True

        file_age = datetime.now() - datetime.fromtimestamp(cassette_file.stat().st_mtime)
        return file_age.days > self.refresh_interval_days

    def refresh_cassettes(self, cassette_dir: Path):
        """Refresh outdated cassettes."""
        for cassette_file in cassette_dir.glob("*.json"):
            if self.should_refresh_cassette(cassette_file):
                self._refresh_cassette(cassette_file)

    def _refresh_cassette(self, cassette_file: Path):
        """Refresh individual cassette."""
        # Remove outdated cassette
        cassette_file.unlink()

        # Log refresh action
        logger.info(f"Refreshed cassette: {cassette_file.name}")
```

---

**Status**: ✅ Production-Ready Fixtures and Test Data Management  
**Last Updated**: September 2024  
**Version**: 1.0.0
