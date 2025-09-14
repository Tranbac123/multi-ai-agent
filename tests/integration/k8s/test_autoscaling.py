"""Test autoscaling configurations and functionality."""

import pytest
import yaml
from pathlib import Path
from typing import Dict, List, Any


class TestKEDAConfiguration:
    """Test KEDA autoscaling configurations."""

    @pytest.fixture
    def keda_config(self):
        """Load KEDA configuration."""
        config_path = Path(__file__).parent.parent.parent / "infra" / "k8s" / "autoscaling" / "enhanced-keda.yaml"
        with open(config_path, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_keda_scaled_objects_exist(self, keda_config):
        """Test that all required KEDA ScaledObjects exist."""
        scaled_objects = [obj for obj in keda_config if obj.get('kind') == 'ScaledObject']
        
        expected_services = [
            'orchestrator-enhanced-scaler',
            'router-service-enhanced-scaler',
            'realtime-enhanced-scaler',
            'analytics-service-enhanced-scaler',
            'billing-service-enhanced-scaler'
        ]
        
        actual_scalers = [obj['metadata']['name'] for obj in scaled_objects]
        
        for expected in expected_services:
            assert expected in actual_scalers, f"Missing ScaledObject: {expected}"

    def test_orchestrator_keda_configuration(self, keda_config):
        """Test orchestrator KEDA configuration."""
        orchestrator_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'orchestrator-enhanced-scaler'
        )
        
        spec = orchestrator_scaler['spec']
        
        # Check basic scaling parameters
        assert spec['minReplicaCount'] == 2
        assert spec['maxReplicaCount'] == 50
        assert spec['pollingInterval'] == 15
        assert spec['cooldownPeriod'] == 300
        assert spec['idleReplicaCount'] == 2
        
        # Check triggers
        triggers = spec['triggers']
        assert len(triggers) >= 3  # Should have NATS, CPU, and Memory triggers
        
        # Check NATS JetStream trigger
        nats_trigger = next((t for t in triggers if t['type'] == 'nats-jetstream'), None)
        assert nats_trigger is not None
        assert nats_trigger['metadata']['stream'] == 'orchestrator'
        assert nats_trigger['metadata']['lagThreshold'] == '10'
        
        # Check Prometheus triggers
        prometheus_triggers = [t for t in triggers if t['type'] == 'prometheus']
        assert len(prometheus_triggers) >= 2  # CPU and Memory

    def test_router_service_keda_configuration(self, keda_config):
        """Test router service KEDA configuration."""
        router_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'router-service-enhanced-scaler'
        )
        
        spec = router_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 2
        assert spec['maxReplicaCount'] == 30
        assert spec['pollingInterval'] == 15
        
        # Check triggers
        triggers = spec['triggers']
        prometheus_triggers = [t for t in triggers if t['type'] == 'prometheus']
        
        # Should have request rate, latency, and error rate triggers
        trigger_names = [t['metadata']['metricName'] for t in prometheus_triggers]
        expected_metrics = [
            'router_requests_per_second',
            'router_decision_latency_p95',
            'router_error_rate'
        ]
        
        for metric in expected_metrics:
            assert metric in trigger_names

    def test_realtime_keda_configuration(self, keda_config):
        """Test realtime service KEDA configuration."""
        realtime_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'realtime-enhanced-scaler'
        )
        
        spec = realtime_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 2
        assert spec['maxReplicaCount'] == 40
        
        # Check triggers
        triggers = spec['triggers']
        
        # Should have WebSocket connections, Redis queue, and backpressure triggers
        trigger_types = [t['type'] for t in triggers]
        assert 'prometheus' in trigger_types
        assert 'redis' in trigger_types
        
        # Check WebSocket connections trigger
        ws_trigger = next((t for t in triggers if t['metadata'].get('metricName') == 'websocket_connections_active'), None)
        assert ws_trigger is not None
        assert ws_trigger['metadata']['threshold'] == '200'

    def test_analytics_keda_configuration(self, keda_config):
        """Test analytics service KEDA configuration."""
        analytics_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'analytics-service-enhanced-scaler'
        )
        
        spec = analytics_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 20
        assert spec['pollingInterval'] == 30  # Longer interval for analytics
        
        # Check triggers
        triggers = spec['triggers']
        prometheus_triggers = [t for t in triggers if t['type'] == 'prometheus']
        
        # Should have query rate, latency, and cache hit rate triggers
        trigger_names = [t['metadata']['metricName'] for t in prometheus_triggers]
        expected_metrics = [
            'analytics_queries_per_second',
            'analytics_query_latency_p95',
            'analytics_cache_hit_rate'
        ]
        
        for metric in expected_metrics:
            assert metric in trigger_names

    def test_billing_keda_configuration(self, keda_config):
        """Test billing service KEDA configuration."""
        billing_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'billing-service-enhanced-scaler'
        )
        
        spec = billing_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 10
        
        # Check triggers
        triggers = spec['triggers']
        
        # Should have Redis queue, transaction rate, and invoice rate triggers
        trigger_types = [t['type'] for t in triggers]
        assert 'redis' in trigger_types
        assert 'prometheus' in trigger_types
        
        # Check Redis queue trigger
        redis_trigger = next((t for t in triggers if t['type'] == 'redis'), None)
        assert redis_trigger is not None
        assert redis_trigger['metadata']['listName'] == 'billing_queue'

    def test_scaled_job_configuration(self, keda_config):
        """Test ScaledJob configuration for batch processing."""
        scaled_jobs = [obj for obj in keda_config if obj.get('kind') == 'ScaledJob']
        
        assert len(scaled_jobs) >= 1
        
        batch_scaler = next(
            obj for obj in scaled_jobs 
            if obj['metadata']['name'] == 'batch-processor-scaler'
        )
        
        spec = batch_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 0
        assert spec['maxReplicaCount'] == 10
        assert spec['pollingInterval'] == 30
        
        # Check job configuration
        job_target = spec['jobTargetRef']
        assert job_target['parallelism'] == 1
        assert job_target['completions'] == 1
        assert job_target['activeDeadlineSeconds'] == 3600
        assert job_target['backoffLimit'] == 3

    def test_database_pool_scaling(self, keda_config):
        """Test database connection pool scaling."""
        db_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'database-pool-scaler'
        )
        
        spec = db_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 5
        
        # Check PostgreSQL trigger
        triggers = spec['triggers']
        postgres_trigger = next((t for t in triggers if t['type'] == 'postgresql'), None)
        assert postgres_trigger is not None
        assert 'connection' in postgres_trigger['metadata']
        assert 'query' in postgres_trigger['metadata']

    def test_redis_pool_scaling(self, keda_config):
        """Test Redis connection pool scaling."""
        redis_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'redis-pool-scaler'
        )
        
        spec = redis_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 3
        
        # Check Redis trigger
        triggers = spec['triggers']
        redis_trigger = next((t for t in triggers if t['type'] == 'redis'), None)
        assert redis_trigger is not None
        assert redis_trigger['metadata']['listName'] == 'connection_pool'

    def test_nats_jetstream_scaling(self, keda_config):
        """Test NATS JetStream scaling."""
        nats_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'nats-jetstream-scaler'
        )
        
        spec = nats_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 3
        
        # Check NATS JetStream trigger
        triggers = spec['triggers']
        nats_trigger = next((t for t in triggers if t['type'] == 'nats-jetstream'), None)
        assert nats_trigger is not None
        assert nats_trigger['metadata']['stream'] == 'system'

    def test_monitoring_scaling(self, keda_config):
        """Test monitoring service scaling."""
        monitoring_scaler = next(
            obj for obj in keda_config 
            if obj.get('kind') == 'ScaledObject' and 
            obj['metadata']['name'] == 'monitoring-scaler'
        )
        
        spec = monitoring_scaler['spec']
        
        # Check scaling parameters
        assert spec['minReplicaCount'] == 1
        assert spec['maxReplicaCount'] == 3
        assert spec['pollingInterval'] == 60  # Longer interval for monitoring
        
        # Check triggers
        triggers = spec['triggers']
        prometheus_triggers = [t for t in triggers if t['type'] == 'prometheus']
        assert len(prometheus_triggers) >= 2


class TestHPAConfiguration:
    """Test HPA autoscaling configurations."""

    @pytest.fixture
    def hpa_config(self):
        """Load HPA configuration."""
        config_path = Path(__file__).parent.parent.parent / "infra" / "k8s" / "autoscaling" / "enhanced-hpa.yaml"
        with open(config_path, 'r') as f:
            return list(yaml.safe_load_all(f))

    def test_hpa_resources_exist(self, hpa_config):
        """Test that all required HPA resources exist."""
        hpa_resources = [obj for obj in hpa_config if obj.get('kind') == 'HorizontalPodAutoscaler']
        
        expected_hpas = [
            'api-gateway-enhanced-hpa',
            'router-service-enhanced-hpa',
            'orchestrator-enhanced-hpa',
            'realtime-enhanced-hpa',
            'analytics-service-enhanced-hpa',
            'billing-service-enhanced-hpa'
        ]
        
        actual_hpas = [obj['metadata']['name'] for obj in hpa_resources]
        
        for expected in expected_hpas:
            assert expected in actual_hpas, f"Missing HPA: {expected}"

    def test_api_gateway_hpa_configuration(self, hpa_config):
        """Test API Gateway HPA configuration."""
        api_hpa = next(
            obj for obj in hpa_config 
            if obj.get('kind') == 'HorizontalPodAutoscaler' and 
            obj['metadata']['name'] == 'api-gateway-enhanced-hpa'
        )
        
        spec = api_hpa['spec']
        
        # Check scaling parameters
        assert spec['minReplicas'] == 2
        assert spec['maxReplicas'] == 20
        
        # Check metrics
        metrics = spec['metrics']
        metric_types = [m['type'] for m in metrics]
        assert 'Resource' in metric_types
        assert 'Pods' in metric_types
        
        # Check CPU and Memory metrics
        resource_metrics = [m for m in metrics if m['type'] == 'Resource']
        resource_names = [m['resource']['name'] for m in resource_metrics]
        assert 'cpu' in resource_names
        assert 'memory' in resource_names
        
        # Check custom metrics
        pod_metrics = [m for m in metrics if m['type'] == 'Pods']
        pod_metric_names = [m['pods']['metric']['name'] for m in pod_metrics]
        assert 'requests_per_second' in pod_metric_names
        assert 'response_time_p95' in pod_metric_names

    def test_router_service_hpa_configuration(self, hpa_config):
        """Test Router Service HPA configuration."""
        router_hpa = next(
            obj for obj in hpa_config 
            if obj.get('kind') == 'HorizontalPodAutoscaler' and 
            obj['metadata']['name'] == 'router-service-enhanced-hpa'
        )
        
        spec = router_hpa['spec']
        
        # Check scaling parameters
        assert spec['minReplicas'] == 2
        assert spec['maxReplicas'] == 30
        
        # Check custom metrics
        metrics = spec['metrics']
        pod_metrics = [m for m in metrics if m['type'] == 'Pods']
        pod_metric_names = [m['pods']['metric']['name'] for m in pod_metrics]
        
        assert 'router_decision_latency_p95' in pod_metric_names
        assert 'router_misroute_rate' in pod_metric_names

    def test_orchestrator_hpa_configuration(self, hpa_config):
        """Test Orchestrator HPA configuration."""
        orchestrator_hpa = next(
            obj for obj in hpa_config 
            if obj.get('kind') == 'HorizontalPodAutoscaler' and 
            obj['metadata']['name'] == 'orchestrator-enhanced-hpa'
        )
        
        spec = orchestrator_hpa['spec']
        
        # Check scaling parameters
        assert spec['minReplicas'] == 2
        assert spec['maxReplicas'] == 50
        
        # Check external metrics
        metrics = spec['metrics']
        external_metrics = [m for m in metrics if m['type'] == 'External']
        external_metric_names = [m['external']['metric']['name'] for m in external_metrics]
        
        assert 'nats_jetstream_queue_depth' in external_metric_names

    def test_realtime_hpa_configuration(self, hpa_config):
        """Test Realtime Service HPA configuration."""
        realtime_hpa = next(
            obj for obj in hpa_config 
            if obj.get('kind') == 'HorizontalPodAutoscaler' and 
            obj['metadata']['name'] == 'realtime-enhanced-hpa'
        )
        
        spec = realtime_hpa['spec']
        
        # Check scaling parameters
        assert spec['minReplicas'] == 2
        assert spec['maxReplicas'] == 40
        
        # Check WebSocket metrics
        metrics = spec['metrics']
        pod_metrics = [m for m in metrics if m['type'] == 'Pods']
        pod_metric_names = [m['pods']['metric']['name'] for m in pod_metrics]
        
        assert 'websocket_connections_active' in pod_metric_names

    def test_vpa_configuration(self, hpa_config):
        """Test VPA (Vertical Pod Autoscaler) configuration."""
        vpa_resources = [obj for obj in hpa_config if obj.get('kind') == 'VerticalPodAutoscaler']
        
        assert len(vpa_resources) >= 4  # Should have VPA for major services
        
        # Check API Gateway VPA
        api_vpa = next(
            obj for obj in vpa_resources 
            if obj['metadata']['name'] == 'api-gateway-vpa'
        )
        
        spec = api_vpa['spec']
        assert spec['updatePolicy']['updateMode'] == 'Auto'
        
        # Check resource policy
        resource_policy = spec['resourcePolicy']['containerPolicies'][0]
        assert 'minAllowed' in resource_policy
        assert 'maxAllowed' in resource_policy
        assert resource_policy['controlledResources'] == ['cpu', 'memory']

    def test_behavior_configuration(self, hpa_config):
        """Test HPA behavior configuration."""
        api_hpa = next(
            obj for obj in hpa_config 
            if obj.get('kind') == 'HorizontalPodAutoscaler' and 
            obj['metadata']['name'] == 'api-gateway-enhanced-hpa'
        )
        
        spec = api_hpa['spec']
        
        # Check behavior configuration
        assert 'behavior' in spec
        behavior = spec['behavior']
        
        # Check scale down behavior
        assert 'scaleDown' in behavior
        scale_down = behavior['scaleDown']
        assert scale_down['stabilizationWindowSeconds'] == 300
        
        # Check scale up behavior
        assert 'scaleUp' in behavior
        scale_up = behavior['scaleUp']
        assert scale_up['stabilizationWindowSeconds'] == 60

    def test_cluster_autoscaler_configuration(self, hpa_config):
        """Test Cluster Autoscaler configuration."""
        config_maps = [obj for obj in hpa_config if obj.get('kind') == 'ConfigMap']
        
        cluster_autoscaler_config = next(
            obj for obj in config_maps 
            if obj['metadata']['name'] == 'cluster-autoscaler-status'
        )
        
        data = cluster_autoscaler_config['data']
        
        # Check cluster autoscaler settings
        assert 'nodes.min' in data
        assert 'nodes.max' in data
        assert 'scale-down-enabled' in data
        assert data['scale-down-enabled'] == 'true'

    def test_metric_targets_are_valid(self, hpa_config):
        """Test that all metric targets have valid values."""
        hpa_resources = [obj for obj in hpa_config if obj.get('kind') == 'HorizontalPodAutoscaler']
        
        for hpa in hpa_resources:
            spec = hpa['spec']
            metrics = spec.get('metrics', [])
            
            for metric in metrics:
                # Check Resource metrics
                if metric['type'] == 'Resource':
                    target = metric['resource']['target']
                    if target['type'] == 'Utilization':
                        utilization = target['averageUtilization']
                        assert 1 <= utilization <= 100
                
                # Check Pods metrics
                elif metric['type'] == 'Pods':
                    target = metric['pods']['target']
                    if target['type'] == 'AverageValue':
                        # Should be a valid quantity string
                        value = target['averageValue']
                        assert isinstance(value, str)
                        assert len(value) > 0
                
                # Check External metrics
                elif metric['type'] == 'External':
                    target = metric['external']['target']
                    if target['type'] == 'AverageValue':
                        value = target['averageValue']
                        assert isinstance(value, str)
                        assert len(value) > 0

    def test_scaling_policies_are_valid(self, hpa_config):
        """Test that scaling policies have valid configurations."""
        hpa_resources = [obj for obj in hpa_config if obj.get('kind') == 'HorizontalPodAutoscaler']
        
        for hpa in hpa_resources:
            spec = hpa['spec']
            behavior = spec.get('behavior', {})
            
            for direction in ['scaleUp', 'scaleDown']:
                if direction in behavior:
                    policy = behavior[direction]
                    
                    # Check stabilization window
                    if 'stabilizationWindowSeconds' in policy:
                        window = policy['stabilizationWindowSeconds']
                        assert window > 0
                    
                    # Check policies
                    if 'policies' in policy:
                        for policy_item in policy['policies']:
                            assert 'type' in policy_item
                            assert 'value' in policy_item
                            assert 'periodSeconds' in policy_item
                            
                            # Check policy values
                            value = policy_item['value']
                            period = policy_item['periodSeconds']
                            
                            assert value > 0
                            assert period > 0
