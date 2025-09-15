# Security Testing

## 🛡️ **Overview**

This document defines comprehensive security testing requirements for the Multi-AI-Agent platform, covering multi-tenant isolation, data protection, and compliance validation.

## 🎯 **Security Testing Objectives**

### **Primary Goals**

- **Tenant Isolation**: Ensure complete data separation between tenants
- **Data Protection**: Validate PII detection and redaction
- **Access Control**: Verify authentication and authorization
- **Compliance**: Meet SOC 2, GDPR, and other regulatory requirements

### **Security Testing Categories**

- **Multi-Tenant Security**: RLS, cross-tenant access prevention
- **Data Protection**: PII/DLP, encryption, data residency
- **API Security**: Authentication, authorization, rate limiting
- **Infrastructure Security**: Container scanning, secret management

## 🔒 **Multi-Tenant Security Tests**

### **Row-Level Security (RLS) Tests**

#### **Test 1: Cross-Tenant Data Access Prevention**

```python
def test_cross_tenant_data_access_prevention():
    """Test that tenants cannot access each other's data."""
    # Setup test data
    tenant_a_data = create_tenant_data("tenant_a")
    tenant_b_data = create_tenant_data("tenant_b")

    # Attempt cross-tenant access
    with tenant_context("tenant_a"):
        # Should only see tenant A data
        results = query_database("SELECT * FROM agent_runs")
        assert all(r["tenant_id"] == "tenant_a" for r in results)

        # Should not see tenant B data
        tenant_b_results = query_database(
            "SELECT * FROM agent_runs WHERE tenant_id = 'tenant_b'"
        )
        assert len(tenant_b_results) == 0

    # Verify audit trail
    audit_logs = get_audit_logs("tenant_a")
    assert any("cross_tenant_access_attempt" in log for log in audit_logs)
```

#### **Test 2: RLS Policy Enforcement**

```python
def test_rls_policy_enforcement():
    """Test that RLS policies are properly enforced."""
    # Test user access within tenant
    with tenant_context("tenant_123"):
        with user_context("user_456"):
            # Should access user's own data
            user_data = query_database(
                "SELECT * FROM agent_runs WHERE user_id = 'user_456'"
            )
            assert len(user_data) > 0

            # Should not access other users' data
            other_user_data = query_database(
                "SELECT * FROM agent_runs WHERE user_id = 'user_789'"
            )
            assert len(other_user_data) == 0
```

#### **Test 3: Tenant Context Validation**

```python
def test_tenant_context_validation():
    """Test that tenant context is properly validated."""
    # Test missing tenant context
    with pytest.raises(TenantContextError):
        query_database("SELECT * FROM agent_runs")

    # Test invalid tenant context
    with pytest.raises(TenantContextError):
        with tenant_context("invalid_tenant"):
            query_database("SELECT * FROM agent_runs")
```

### **Quota Enforcement Tests**

#### **Test 4: Rate Limiting Validation**

```python
def test_rate_limiting_enforcement():
    """Test that rate limiting is properly enforced."""
    tenant_id = "tenant_123"
    rate_limit = 100  # requests per minute

    # Send requests up to rate limit
    for i in range(rate_limit):
        response = api_client.post("/api/chat",
            headers={"X-Tenant-ID": tenant_id},
            json={"message": "test message"}
        )
        assert response.status_code == 200

    # Exceed rate limit
    response = api_client.post("/api/chat",
        headers={"X-Tenant-ID": tenant_id},
        json={"message": "test message"}
    )
    assert response.status_code == 429
    assert "rate_limit_exceeded" in response.json()["error"]["code"]

    # Verify rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
```

#### **Test 5: Quota Usage Tracking**

```python
def test_quota_usage_tracking():
    """Test that quota usage is properly tracked."""
    tenant_id = "tenant_123"
    initial_quota = get_tenant_quota_usage(tenant_id)

    # Make API requests
    for i in range(10):
        api_client.post("/api/chat",
            headers={"X-Tenant-ID": tenant_id},
            json={"message": "test message"}
        )

    # Verify quota usage increased
    updated_quota = get_tenant_quota_usage(tenant_id)
    assert updated_quota["requests"] == initial_quota["requests"] + 10
    assert updated_quota["cost"] > initial_quota["cost"]
```

## 🔐 **Data Protection Tests**

### **PII Detection and Redaction Tests**

#### **Test 6: PII Detection**

```python
def test_pii_detection():
    """Test that PII is properly detected."""
    test_cases = [
        {
            "input": "My email is john.doe@example.com",
            "expected_pii": ["john.doe@example.com"],
            "expected_type": "email"
        },
        {
            "input": "Call me at 555-123-4567",
            "expected_pii": ["555-123-4567"],
            "expected_type": "phone"
        },
        {
            "input": "My SSN is 123-45-6789",
            "expected_pii": ["123-45-6789"],
            "expected_type": "ssn"
        },
        {
            "input": "Credit card: 4111-1111-1111-1111",
            "expected_pii": ["4111-1111-1111-1111"],
            "expected_type": "credit_card"
        }
    ]

    for case in test_cases:
        detected_pii = detect_pii(case["input"])
        assert len(detected_pii) == 1
        assert detected_pii[0]["value"] == case["expected_pii"][0]
        assert detected_pii[0]["type"] == case["expected_type"]
```

#### **Test 7: PII Redaction**

```python
def test_pii_redaction():
    """Test that PII is properly redacted."""
    test_cases = [
        {
            "input": "My email is john.doe@example.com",
            "expected_output": "My email is [REDACTED]",
            "redaction_level": "full"
        },
        {
            "input": "Call me at 555-123-4567",
            "expected_output": "Call me at [REDACTED]",
            "redaction_level": "full"
        },
        {
            "input": "My email is john.doe@example.com and phone is 555-123-4567",
            "expected_output": "My email is [REDACTED] and phone is [REDACTED]",
            "redaction_level": "full"
        }
    ]

    for case in test_cases:
        redacted = redact_pii(case["input"], case["redaction_level"])
        assert redacted == case["expected_output"]
        assert "[REDACTED]" in redacted
        assert not re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', redacted)
```

#### **Test 8: Log PII Redaction**

```python
def test_log_pii_redaction():
    """Test that logs are properly redacted."""
    # Generate log entry with PII
    log_entry = {
        "timestamp": "2024-09-14T10:30:00Z",
        "level": "INFO",
        "message": "User john.doe@example.com requested password reset",
        "user_id": "user_123",
        "tenant_id": "tenant_456"
    }

    # Process log entry
    processed_log = process_log_entry(log_entry)

    # Verify PII is redacted
    assert "[REDACTED]" in processed_log["message"]
    assert "john.doe@example.com" not in processed_log["message"]

    # Verify non-PII fields are preserved
    assert processed_log["user_id"] == "user_123"
    assert processed_log["tenant_id"] == "tenant_456"
```

### **Data Loss Prevention (DLP) Tests**

#### **Test 9: DLP Policy Enforcement**

```python
def test_dlp_policy_enforcement():
    """Test that DLP policies are properly enforced."""
    # Test credit card detection
    response = api_client.post("/api/chat",
        json={"message": "My credit card is 4111-1111-1111-1111"}
    )

    assert response.status_code == 400
    assert "dlp_violation" in response.json()["error"]["code"]
    assert "credit_card_detected" in response.json()["error"]["message"]

    # Test SSN detection
    response = api_client.post("/api/chat",
        json={"message": "My SSN is 123-45-6789"}
    )

    assert response.status_code == 400
    assert "dlp_violation" in response.json()["error"]["code"]
    assert "ssn_detected" in response.json()["error"]["message"]
```

## 🔑 **API Security Tests**

### **Authentication Tests**

#### **Test 10: JWT Token Validation**

```python
def test_jwt_token_validation():
    """Test JWT token validation."""
    # Test valid token
    valid_token = generate_jwt_token("user_123", "tenant_456")
    response = api_client.get("/api/user/profile",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 200

    # Test invalid token
    invalid_token = "invalid_token"
    response = api_client.get("/api/user/profile",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    assert "invalid_token" in response.json()["error"]["code"]

    # Test expired token
    expired_token = generate_jwt_token("user_123", "tenant_456", exp=-1)
    response = api_client.get("/api/user/profile",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "token_expired" in response.json()["error"]["code"]
```

#### **Test 11: API Key Validation**

```python
def test_api_key_validation():
    """Test API key validation."""
    # Test valid API key
    valid_api_key = generate_api_key("tenant_456")
    response = api_client.post("/api/chat",
        headers={"X-API-Key": valid_api_key},
        json={"message": "test message"}
    )
    assert response.status_code == 200

    # Test invalid API key
    invalid_api_key = "invalid_api_key"
    response = api_client.post("/api/chat",
        headers={"X-API-Key": invalid_api_key},
        json={"message": "test message"}
    )
    assert response.status_code == 401
    assert "invalid_api_key" in response.json()["error"]["code"]

    # Test revoked API key
    revoked_api_key = generate_api_key("tenant_456", revoked=True)
    response = api_client.post("/api/chat",
        headers={"X-API-Key": revoked_api_key},
        json={"message": "test message"}
    )
    assert response.status_code == 401
    assert "api_key_revoked" in response.json()["error"]["code"]
```

### **Authorization Tests**

#### **Test 12: Role-Based Access Control**

```python
def test_role_based_access_control():
    """Test role-based access control."""
    # Test admin access
    admin_token = generate_jwt_token("admin_user", "tenant_456", roles=["admin"])
    response = api_client.get("/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Test user access (should be denied)
    user_token = generate_jwt_token("regular_user", "tenant_456", roles=["user"])
    response = api_client.get("/api/admin/users",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert "insufficient_permissions" in response.json()["error"]["code"]
```

#### **Test 13: Resource Access Control**

```python
def test_resource_access_control():
    """Test resource-level access control."""
    # Test user accessing own resources
    user_token = generate_jwt_token("user_123", "tenant_456")
    response = api_client.get("/api/users/user_123/profile",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200

    # Test user accessing other user's resources (should be denied)
    response = api_client.get("/api/users/user_789/profile",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    assert "access_denied" in response.json()["error"]["code"]
```

## 🌐 **Infrastructure Security Tests**

### **Container Security Tests**

#### **Test 14: Container Vulnerability Scanning**

```python
def test_container_vulnerability_scanning():
    """Test container vulnerability scanning."""
    # Scan container images
    scan_results = scan_container_image("multi-ai-agent:latest")

    # Check for critical vulnerabilities
    critical_vulns = [v for v in scan_results["vulnerabilities"]
                     if v["severity"] == "critical"]
    assert len(critical_vulns) == 0, f"Critical vulnerabilities found: {critical_vulns}"

    # Check for high severity vulnerabilities
    high_vulns = [v for v in scan_results["vulnerabilities"]
                 if v["severity"] == "high"]
    assert len(high_vulns) == 0, f"High severity vulnerabilities found: {high_vulns}"
```

#### **Test 15: Secret Management**

```python
def test_secret_management():
    """Test secret management and rotation."""
    # Test secret retrieval
    secret = get_secret("database_password")
    assert secret is not None
    assert len(secret) > 0

    # Test secret rotation
    old_secret = get_secret("api_key")
    rotate_secret("api_key")
    new_secret = get_secret("api_key")

    assert old_secret != new_secret
    assert len(new_secret) > 0
```

## 🔍 **Security Test Execution**

### **Security Test Suite**

```python
class SecurityTestSuite:
    """Comprehensive security test suite."""

    def run_all_security_tests(self):
        """Run all security tests."""
        test_results = {}

        # Multi-tenant security tests
        test_results["multi_tenant"] = self.run_multi_tenant_tests()

        # Data protection tests
        test_results["data_protection"] = self.run_data_protection_tests()

        # API security tests
        test_results["api_security"] = self.run_api_security_tests()

        # Infrastructure security tests
        test_results["infrastructure"] = self.run_infrastructure_tests()

        return test_results

    def run_multi_tenant_tests(self):
        """Run multi-tenant security tests."""
        tests = [
            test_cross_tenant_data_access_prevention,
            test_rls_policy_enforcement,
            test_tenant_context_validation,
            test_rate_limiting_enforcement,
            test_quota_usage_tracking
        ]

        results = []
        for test in tests:
            try:
                test()
                results.append({"test": test.__name__, "status": "passed"})
            except Exception as e:
                results.append({"test": test.__name__, "status": "failed", "error": str(e)})

        return results
```

### **Security Test Reporting**

```python
def generate_security_report(test_results):
    """Generate security test report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "critical_failures": 0
        },
        "categories": {},
        "recommendations": []
    }

    for category, results in test_results.items():
        category_summary = {
            "total": len(results),
            "passed": len([r for r in results if r["status"] == "passed"]),
            "failed": len([r for r in results if r["status"] == "failed"])
        }

        report["summary"]["total_tests"] += category_summary["total"]
        report["summary"]["passed"] += category_summary["passed"]
        report["summary"]["failed"] += category_summary["failed"]

        report["categories"][category] = {
            "summary": category_summary,
            "results": results
        }

    # Generate recommendations
    if report["summary"]["failed"] > 0:
        report["recommendations"].append("Review failed security tests")

    if report["summary"]["critical_failures"] > 0:
        report["recommendations"].append("Address critical security failures immediately")

    return report
```

## 🚨 **Security Test Alerts**

### **Security Test Failure Alerts**

```yaml
alerts:
  - name: "Security Test Failure"
    condition: "security_test_failed == 1"
    severity: "critical"
    description: "Security test failed"

  - name: "Cross-Tenant Access Detected"
    condition: "cross_tenant_access_detected == 1"
    severity: "critical"
    description: "Cross-tenant data access detected"

  - name: "PII Leakage Detected"
    condition: "pii_leakage_detected == 1"
    severity: "critical"
    description: "PII leakage detected in logs or responses"

  - name: "Authentication Failure"
    condition: "authentication_failure_rate > 0.1"
    severity: "warning"
    description: "High authentication failure rate"
```

---

**Status**: ✅ Production-Ready Security Testing  
**Last Updated**: September 2024  
**Version**: 1.0.0
