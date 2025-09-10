"""Integration tests for autoscaling and security configurations."""

import pytest
import asyncio
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp


class TestKEDAConfiguration:
    """Test KEDA autoscaling configuration."""
    
    def test_keda_scaled_objects_valid(self):
        """Test that KEDA ScaledObjects are valid YAML."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        enhanced_keda_file = Path("infra/k8s/autoscaling/enhanced-keda.yaml")
        
        for file_path in [keda_file, enhanced_keda_file]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                
                # Check for ScaledObjects
                scaled_objects = [doc for doc in documents if doc.get('kind') == 'ScaledObject']
                assert len(scaled_objects) > 0, f"No ScaledObjects found in {file_path}"
                
                for scaled_object in scaled_objects:
                    # Validate required fields
                    assert 'metadata' in scaled_object
                    assert 'name' in scaled_object['metadata']
                    assert 'spec' in scaled_object
                    
                    spec = scaled_object['spec']
                    assert 'scaleTargetRef' in spec
                    assert 'minReplicaCount' in spec
                    assert 'maxReplicaCount' in spec
                    assert 'triggers' in spec
                    
                    # Validate triggers
                    triggers = spec['triggers']
                    assert len(triggers) > 0, "No triggers defined"
                    
                    for trigger in triggers:
                        assert 'type' in trigger
                        assert 'metadata' in trigger
                        
                        # Validate trigger types
                        valid_types = [
                            'nats-jetstream', 'prometheus', 'redis', 
                            'postgresql', 'cpu', 'memory'
                        ]
                        assert trigger['type'] in valid_types, f"Invalid trigger type: {trigger['type']}"


class TestHPAConfiguration:
    """Test HPA configuration."""
    
    def test_hpa_configurations_valid(self):
        """Test that HPA configurations are valid YAML."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        enhanced_hpa_file = Path("infra/k8s/autoscaling/enhanced-hpa.yaml")
        
        for file_path in [hpa_file, enhanced_hpa_file]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                
                # Check for HPAs
                hpas = [doc for doc in documents if doc.get('kind') == 'HorizontalPodAutoscaler']
                assert len(hpas) > 0, f"No HPAs found in {file_path}"
                
                for hpa in hpas:
                    # Validate required fields
                    assert 'metadata' in hpa
                    assert 'name' in hpa['metadata']
                    assert 'spec' in hpa
                    
                    spec = hpa['spec']
                    assert 'scaleTargetRef' in spec
                    assert 'minReplicas' in spec
                    assert 'maxReplicas' in spec
                    assert 'metrics' in spec
                    
                    # Validate metrics
                    metrics = spec['metrics']
                    assert len(metrics) > 0, "No metrics defined"
                    
                    for metric in metrics:
                        assert 'type' in metric
                        
                        # Validate metric types
                        valid_types = ['Resource', 'Pods', 'External', 'Object']
                        assert metric['type'] in valid_types, f"Invalid metric type: {metric['type']}"


class TestNetworkPolicyConfiguration:
    """Test NetworkPolicy configuration."""
    
    def test_network_policies_valid(self):
        """Test that NetworkPolicies are valid YAML."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        
        if netpol_file.exists():
            with open(netpol_file, 'r') as f:
                documents = list(yaml.safe_load_all(f))
            
            # Check for NetworkPolicies
            netpols = [doc for doc in documents if doc.get('kind') == 'NetworkPolicy']
            assert len(netpols) > 0, "No NetworkPolicies found"
            
            for netpol in netpols:
                # Validate required fields
                assert 'metadata' in netpol
                assert 'name' in netpol['metadata']
                assert 'spec' in netpol
                
                spec = netpol['spec']
                assert 'podSelector' in spec
                assert 'policyTypes' in spec
                
                # Validate policy types
                valid_types = ['Ingress', 'Egress']
                for policy_type in spec['policyTypes']:
                    assert policy_type in valid_types, f"Invalid policy type: {policy_type}"


class TestHealthChecker:
    """Test health checker functionality."""
    
    @pytest.fixture
    def health_checker(self):
        """Create a health checker instance."""
        import sys
        import os
        sys.path.append(os.path.join(os.getcwd(), 'infra', 'k8s', 'health'))
        from enhanced_health_checker import EnhancedHealthChecker, HealthCheck
        return EnhancedHealthChecker()
    
    @pytest.fixture
    def sample_health_checks(self):
        """Create sample health checks for testing."""
        import sys
        import os
        sys.path.append(os.path.join(os.getcwd(), 'infra', 'k8s', 'health'))
        from enhanced_health_checker import HealthCheck
        return [
            HealthCheck(
                name="test-service",
                url="http://test-service:8000/health",
                expected_status=200,
                expected_response={"status": "ok"},
                critical=True
            ),
            HealthCheck(
                name="test-service-ready",
                url="http://test-service:8000/health/ready",
                expected_status=200,
                critical=True
            )
        ]
    
    @pytest.mark.asyncio
    async def test_health_checker_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.session is None
        assert health_checker.health_checks == []
        assert health_checker.results == []
    
    @pytest.mark.asyncio
    async def test_add_health_check(self, health_checker, sample_health_checks):
        """Test adding health checks."""
        for health_check in sample_health_checks:
            health_checker.add_health_check(health_check)
        
        assert len(health_checker.health_checks) == 2
        assert health_checker.health_checks[0].name == "test-service"
        assert health_checker.health_checks[1].name == "test-service-ready"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, health_checker, sample_health_checks):
        """Test successful health check."""
        health_checker.add_health_check(sample_health_checks[0])
        
        # Mock successful response
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(sample_health_checks[0])
                
                assert result.name == "test-service"
                assert result.status.value == "healthy"
                assert result.response_time > 0
                assert result.error is None
                assert result.details == {"status": "ok"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])