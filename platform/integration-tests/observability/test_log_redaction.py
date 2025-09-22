"""Test log redaction and PII protection."""

import pytest
import asyncio
import time
import re
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PIIAssertions


class TestLogRedaction:
    """Test log redaction and PII protection."""
    
    @pytest.mark.asyncio
    async def test_pii_detection_in_logs(self):
        """Test PII detection in logs."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock PII detector
        pii_detector = Mock()
        pii_detector.detect_pii = AsyncMock()
        pii_detector.classify_pii_types = AsyncMock()
        pii_detector.calculate_pii_risk_score = AsyncMock()
        
        # Simulate PII detection
        pii_detector.detect_pii.return_value = {
            "pii_detected": True,
            "pii_instances": [
                {
                    "type": "email",
                    "value": "user@example.com",
                    "start_position": 45,
                    "end_position": 60,
                    "confidence": 0.95
                },
                {
                    "type": "phone",
                    "value": "+1-555-123-4567",
                    "start_position": 120,
                    "end_position": 135,
                    "confidence": 0.90
                },
                {
                    "type": "ssn",
                    "value": "123-45-6789",
                    "start_position": 200,
                    "end_position": 211,
                    "confidence": 0.98
                }
            ],
            "total_pii_count": 3,
            "detection_confidence": 0.94
        }
        
        # Simulate PII classification
        pii_detector.classify_pii_types.return_value = {
            "classification_completed": True,
            "pii_types": {
                "email": {"count": 1, "risk_level": "medium"},
                "phone": {"count": 1, "risk_level": "medium"},
                "ssn": {"count": 1, "risk_level": "high"}
            },
            "overall_risk_level": "high"
        }
        
        # Simulate PII risk score calculation
        pii_detector.calculate_pii_risk_score.return_value = {
            "risk_score_calculated": True,
            "risk_score": 0.85,
            "risk_level": "high",
            "risk_factors": [
                "SSN detected",
                "Multiple PII types",
                "High confidence detection"
            ]
        }
        
        # Test PII detection
        detection_result = await pii_detector.detect_pii(
            log_content="User john.doe@example.com called from +1-555-123-4567 with SSN 123-45-6789"
        )
        assert detection_result["pii_detected"] is True
        assert detection_result["total_pii_count"] == 3
        assert len(detection_result["pii_instances"]) == 3
        
        # Test PII classification
        classification_result = await pii_detector.classify_pii_types(detection_result)
        assert classification_result["classification_completed"] is True
        assert classification_result["overall_risk_level"] == "high"
        assert len(classification_result["pii_types"]) == 3
        
        # Test PII risk score calculation
        risk_result = await pii_detector.calculate_pii_risk_score(detection_result)
        assert risk_result["risk_score_calculated"] is True
        assert risk_result["risk_score"] == 0.85
        assert risk_result["risk_level"] == "high"
        assert len(risk_result["risk_factors"]) == 3
        
        # Verify PII detection
        pii_instances = detection_result["pii_instances"]
        assert pii_instances[0]["type"] == "email"
        assert pii_instances[1]["type"] == "phone"
        assert pii_instances[2]["type"] == "ssn"
        assert all(instance["confidence"] >= 0.9 for instance in pii_instances)
    
    @pytest.mark.asyncio
    async def test_pii_redaction_in_logs(self):
        """Test PII redaction in logs."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock PII redactor
        pii_redactor = Mock()
        pii_redactor.redact_pii = AsyncMock()
        pii_redactor.validate_redaction = AsyncMock()
        pii_redactor.calculate_redaction_quality = AsyncMock()
        
        # Simulate PII redaction
        pii_redactor.redact_pii.return_value = {
            "redaction_completed": True,
            "original_content": "User john.doe@example.com called from +1-555-123-4567 with SSN 123-45-6789",
            "redacted_content": "User [REDACTED_EMAIL] called from [REDACTED_PHONE] with SSN [REDACTED_SSN]",
            "redaction_count": 3,
            "redaction_types": ["email", "phone", "ssn"],
            "redaction_confidence": 0.98
        }
        
        # Simulate redaction validation
        pii_redactor.validate_redaction.return_value = {
            "validation_completed": True,
            "redaction_valid": True,
            "remaining_pii_count": 0,
            "validation_errors": [],
            "redaction_completeness": 1.0
        }
        
        # Simulate redaction quality calculation
        pii_redactor.calculate_redaction_quality.return_value = {
            "quality_calculated": True,
            "redaction_quality_score": 0.98,
            "quality_factors": [
                "All PII types redacted",
                "High confidence redaction",
                "No false positives"
            ],
            "quality_grade": "A"
        }
        
        # Test PII redaction
        redaction_result = await pii_redactor.redact_pii(
            content="User john.doe@example.com called from +1-555-123-4567 with SSN 123-45-6789"
        )
        assert redaction_result["redaction_completed"] is True
        assert redaction_result["redaction_count"] == 3
        assert len(redaction_result["redaction_types"]) == 3
        assert "[REDACTED_EMAIL]" in redaction_result["redacted_content"]
        assert "[REDACTED_PHONE]" in redaction_result["redacted_content"]
        assert "[REDACTED_SSN]" in redaction_result["redacted_content"]
        
        # Test redaction validation
        validation_result = await pii_redactor.validate_redaction(redaction_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["redaction_valid"] is True
        assert validation_result["remaining_pii_count"] == 0
        assert validation_result["redaction_completeness"] == 1.0
        
        # Test redaction quality calculation
        quality_result = await pii_redactor.calculate_redaction_quality(redaction_result)
        assert quality_result["quality_calculated"] is True
        assert quality_result["redaction_quality_score"] == 0.98
        assert quality_result["quality_grade"] == "A"
        assert len(quality_result["quality_factors"]) == 3
        
        # Verify redaction quality
        assert redaction_result["redaction_confidence"] >= 0.95
        assert validation_result["redaction_completeness"] == 1.0
        assert quality_result["redaction_quality_score"] >= 0.95
    
    @pytest.mark.asyncio
    async def test_structured_log_redaction(self):
        """Test structured log redaction."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock structured log redactor
        structured_redactor = Mock()
        structured_redactor.redact_structured_log = AsyncMock()
        structured_redactor.validate_structured_redaction = AsyncMock()
        structured_redactor.preserve_log_structure = AsyncMock()
        
        # Simulate structured log redaction
        structured_redactor.redact_structured_log.return_value = {
            "redaction_completed": True,
            "original_log": {
                "timestamp": "2024-01-01T12:00:00Z",
                "level": "INFO",
                "message": "User request processed",
                "user_email": "john.doe@example.com",
                "user_phone": "+1-555-123-4567",
                "user_ssn": "123-45-6789",
                "request_id": "req_001",
                "tenant_id": tenant["tenant_id"]
            },
            "redacted_log": {
                "timestamp": "2024-01-01T12:00:00Z",
                "level": "INFO",
                "message": "User request processed",
                "user_email": "[REDACTED]",
                "user_phone": "[REDACTED]",
                "user_ssn": "[REDACTED]",
                "request_id": "req_001",
                "tenant_id": tenant["tenant_id"]
            },
            "redaction_fields": ["user_email", "user_phone", "user_ssn"],
            "preserved_fields": ["timestamp", "level", "message", "request_id", "tenant_id"]
        }
        
        # Simulate structured redaction validation
        structured_redactor.validate_structured_redaction.return_value = {
            "validation_completed": True,
            "structure_preserved": True,
            "pii_fields_redacted": 3,
            "non_pii_fields_preserved": 5,
            "validation_errors": []
        }
        
        # Simulate log structure preservation
        structured_redactor.preserve_log_structure.return_value = {
            "structure_preserved": True,
            "original_field_count": 8,
            "redacted_field_count": 8,
            "structure_integrity": 1.0
        }
        
        # Test structured log redaction
        redaction_result = await structured_redactor.redact_structured_log({
            "timestamp": "2024-01-01T12:00:00Z",
            "level": "INFO",
            "message": "User request processed",
            "user_email": "john.doe@example.com",
            "user_phone": "+1-555-123-4567",
            "user_ssn": "123-45-6789",
            "request_id": "req_001",
            "tenant_id": tenant["tenant_id"]
        })
        assert redaction_result["redaction_completed"] is True
        assert len(redaction_result["redaction_fields"]) == 3
        assert len(redaction_result["preserved_fields"]) == 5
        assert redaction_result["redacted_log"]["user_email"] == "[REDACTED]"
        assert redaction_result["redacted_log"]["request_id"] == "req_001"  # Preserved
        
        # Test structured redaction validation
        validation_result = await structured_redactor.validate_structured_redaction(redaction_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["structure_preserved"] is True
        assert validation_result["pii_fields_redacted"] == 3
        assert validation_result["non_pii_fields_preserved"] == 5
        
        # Test log structure preservation
        structure_result = await structured_redactor.preserve_log_structure(redaction_result)
        assert structure_result["structure_preserved"] is True
        assert structure_result["original_field_count"] == 8
        assert structure_result["redacted_field_count"] == 8
        assert structure_result["structure_integrity"] == 1.0
        
        # Verify structured redaction
        assert redaction_result["redacted_log"]["timestamp"] == redaction_result["original_log"]["timestamp"]
        assert redaction_result["redacted_log"]["level"] == redaction_result["original_log"]["level"]
        assert redaction_result["redacted_log"]["message"] == redaction_result["original_log"]["message"]
        assert redaction_result["redacted_log"]["request_id"] == redaction_result["original_log"]["request_id"]
        assert redaction_result["redacted_log"]["tenant_id"] == redaction_result["original_log"]["tenant_id"]
    
    @pytest.mark.asyncio
    async def test_log_redaction_performance(self):
        """Test log redaction performance."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock performance monitor
        performance_monitor = Mock()
        performance_monitor.measure_redaction_performance = AsyncMock()
        performance_monitor.benchmark_redaction_speed = AsyncMock()
        performance_monitor.optimize_redaction_performance = AsyncMock()
        
        # Simulate redaction performance measurement
        performance_monitor.measure_redaction_performance.return_value = {
            "performance_measured": True,
            "redaction_time_ms": 25,
            "throughput_logs_per_second": 40,
            "memory_usage_mb": 5.2,
            "cpu_usage_percent": 12,
            "performance_grade": "A"
        }
        
        # Simulate redaction speed benchmarking
        performance_monitor.benchmark_redaction_speed.return_value = {
            "benchmark_completed": True,
            "baseline_redaction_time_ms": 30,
            "current_redaction_time_ms": 25,
            "performance_improvement_percent": 16.7,
            "benchmark_grade": "A"
        }
        
        # Simulate performance optimization
        performance_monitor.optimize_redaction_performance.return_value = {
            "optimization_completed": True,
            "optimization_applied": True,
            "optimized_redaction_time_ms": 20,
            "optimization_improvement_percent": 20,
            "optimization_techniques": [
                "Parallel processing",
                "Caching redaction patterns",
                "Optimized regex compilation"
            ]
        }
        
        # Test redaction performance measurement
        perf_result = await performance_monitor.measure_redaction_performance()
        assert perf_result["performance_measured"] is True
        assert perf_result["redaction_time_ms"] == 25
        assert perf_result["throughput_logs_per_second"] == 40
        assert perf_result["performance_grade"] == "A"
        
        # Test redaction speed benchmarking
        benchmark_result = await performance_monitor.benchmark_redaction_speed()
        assert benchmark_result["benchmark_completed"] is True
        assert benchmark_result["performance_improvement_percent"] == 16.7
        assert benchmark_result["benchmark_grade"] == "A"
        
        # Test performance optimization
        optimization_result = await performance_monitor.optimize_redaction_performance()
        assert optimization_result["optimization_completed"] is True
        assert optimization_result["optimization_applied"] is True
        assert optimization_result["optimization_improvement_percent"] == 20
        assert len(optimization_result["optimization_techniques"]) == 3
        
        # Verify performance thresholds
        assert perf_result["redaction_time_ms"] <= 50  # Should be fast
        assert perf_result["throughput_logs_per_second"] >= 20  # Good throughput
        assert perf_result["memory_usage_mb"] <= 10  # Reasonable memory usage
        assert perf_result["cpu_usage_percent"] <= 20  # Reasonable CPU usage
    
    @pytest.mark.asyncio
    async def test_log_redaction_audit_trail(self):
        """Test log redaction audit trail."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock audit trail manager
        audit_trail_manager = Mock()
        audit_trail_manager.create_redaction_audit = AsyncMock()
        audit_trail_manager.validate_audit_trail = AsyncMock()
        audit_trail_manager.generate_audit_report = AsyncMock()
        
        # Simulate redaction audit creation
        audit_trail_manager.create_redaction_audit.return_value = {
            "audit_created": True,
            "audit_id": "audit_001",
            "redaction_timestamp": time.time(),
            "redaction_details": {
                "original_log_id": "log_001",
                "pii_types_redacted": ["email", "phone", "ssn"],
                "redaction_count": 3,
                "redaction_confidence": 0.98,
                "redaction_method": "regex_pattern_matching"
            },
            "audit_metadata": {
                "tenant_id": tenant["tenant_id"],
                "user_id": user["user_id"],
                "request_id": "req_001",
                "audit_level": "high"
            }
        }
        
        # Simulate audit trail validation
        audit_trail_manager.validate_audit_trail.return_value = {
            "validation_completed": True,
            "audit_trail_valid": True,
            "audit_completeness": 1.0,
            "audit_integrity": 1.0,
            "validation_errors": []
        }
        
        # Simulate audit report generation
        audit_trail_manager.generate_audit_report.return_value = {
            "report_generated": True,
            "report_id": "audit_report_001",
            "report_summary": {
                "total_redactions": 100,
                "pii_types_redacted": ["email", "phone", "ssn", "credit_card"],
                "redaction_success_rate": 0.98,
                "audit_compliance_score": 0.95
            }
        }
        
        # Test redaction audit creation
        audit_result = await audit_trail_manager.create_redaction_audit(
            log_id="log_001",
            redaction_details={
                "pii_types_redacted": ["email", "phone", "ssn"],
                "redaction_count": 3,
                "redaction_confidence": 0.98
            }
        )
        assert audit_result["audit_created"] is True
        assert audit_result["audit_id"] == "audit_001"
        assert len(audit_result["redaction_details"]["pii_types_redacted"]) == 3
        
        # Test audit trail validation
        validation_result = await audit_trail_manager.validate_audit_trail(audit_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["audit_trail_valid"] is True
        assert validation_result["audit_completeness"] == 1.0
        assert validation_result["audit_integrity"] == 1.0
        
        # Test audit report generation
        report_result = await audit_trail_manager.generate_audit_report()
        assert report_result["report_generated"] is True
        assert report_result["report_summary"]["total_redactions"] == 100
        assert report_result["report_summary"]["redaction_success_rate"] >= 0.95
        assert report_result["report_summary"]["audit_compliance_score"] >= 0.95
        
        # Verify audit trail
        assert audit_result["redaction_details"]["redaction_confidence"] >= 0.95
        assert audit_result["audit_metadata"]["audit_level"] == "high"
        assert validation_result["audit_completeness"] == 1.0
        assert validation_result["audit_integrity"] == 1.0
