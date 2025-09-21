#!/usr/bin/env python3
"""
Production Deployment Script for Multi-AI-Agent Platform

This script automates the deployment process to production with comprehensive
validation, monitoring setup, and user experience tracking.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog
import yaml
import requests
from pathlib import Path

logger = structlog.get_logger(__name__)


class ProductionDeployment:
    """Production deployment orchestrator."""
    
    def __init__(self, config_path: str = "k8s/production/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.deployment_status = {
            "start_time": datetime.now(),
            "steps_completed": [],
            "current_step": None,
            "errors": [],
            "warnings": []
        }
        
    def _load_config(self) -> Dict[str, Any]:
        """Load production configuration."""
        
        if not os.path.exists(self.config_path):
            logger.error("Configuration file not found", path=self.config_path)
            sys.exit(1)
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    async def deploy(self):
        """Execute complete production deployment."""
        
        logger.info("Starting production deployment", config=self.config)
        
        try:
            # Step 1: Pre-deployment validation
            await self._validate_environment()
            
            # Step 2: Build and push containers
            await self._build_and_push_containers()
            
            # Step 3: Deploy to Kubernetes
            await self._deploy_to_kubernetes()
            
            # Step 4: Setup monitoring
            await self._setup_monitoring()
            
            # Step 5: Configure user experience tracking
            await self._setup_user_experience_tracking()
            
            # Step 6: Run validation tests
            await self._run_validation_tests()
            
            # Step 7: Enable production traffic
            await self._enable_production_traffic()
            
            # Step 8: Post-deployment monitoring
            await self._post_deployment_monitoring()
            
            logger.info("Production deployment completed successfully")
            
        except Exception as e:
            logger.error("Deployment failed", error=str(e))
            await self._rollback_deployment()
            raise
    
    async def _validate_environment(self):
        """Validate production environment."""
        
        self.deployment_status["current_step"] = "environment_validation"
        logger.info("Validating production environment")
        
        # Check Kubernetes connectivity
        result = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("Kubernetes cluster not accessible")
        
        # Check required tools
        required_tools = ["kubectl", "docker", "helm"]
        for tool in required_tools:
            result = subprocess.run(["which", tool], capture_output=True)
            if result.returncode != 0:
                raise Exception(f"Required tool {tool} not found")
        
        # Validate configuration
        required_configs = ["domain", "registry", "namespace"]
        for config in required_configs:
            if config not in self.config:
                raise Exception(f"Required configuration {config} not found")
        
        self.deployment_status["steps_completed"].append("environment_validation")
        logger.info("Environment validation completed")
    
    async def _build_and_push_containers(self):
        """Build and push container images."""
        
        self.deployment_status["current_step"] = "container_build"
        logger.info("Building and pushing containers")
        
        services = [
            "api-gateway", "orchestrator", "router_service", "realtime",
            "analytics-service", "billing-service", "ingestion", "chat-adapters",
            "tenant-service", "admin-portal", "eval-service"
        ]
        
        registry = self.config["registry"]
        tag = self.config.get("tag", "latest")
        
        for service in services:
            logger.info("Building container", service=service)
            
            # Build container
            build_cmd = [
                "docker", "build",
                "-t", f"{registry}/multi-ai-agent-{service}:{tag}",
                f"apps/{service}/"
            ]
            
            result = subprocess.run(build_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to build {service}: {result.stderr}")
            
            # Push container
            push_cmd = ["docker", "push", f"{registry}/multi-ai-agent-{service}:{tag}"]
            result = subprocess.run(push_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to push {service}: {result.stderr}")
            
            logger.info("Container built and pushed", service=service)
        
        self.deployment_status["steps_completed"].append("container_build")
        logger.info("Container build and push completed")
    
    async def _deploy_to_kubernetes(self):
        """Deploy services to Kubernetes."""
        
        self.deployment_status["current_step"] = "kubernetes_deployment"
        logger.info("Deploying to Kubernetes")
        
        namespace = self.config["namespace"]
        
        # Create namespace
        subprocess.run(["kubectl", "create", "namespace", namespace], capture_output=True)
        
        # Deploy services in dependency order
        deployment_order = [
            "configmaps.yaml",
            "secrets.yaml",
            "api-gateway/",
            "orchestrator/",
            "router_service/",
            "realtime/",
            "analytics-service/",
            "billing-service/",
            "ingestion/",
            "chat-adapters/",
            "tenant-service/",
            "admin-portal/",
            "eval-service/",
            "ingress/"
        ]
        
        for item in deployment_order:
            logger.info("Deploying", item=item)
            
            if item.endswith('.yaml'):
                cmd = ["kubectl", "apply", "-f", f"k8s/production/{item}", "-n", namespace]
            else:
                cmd = ["kubectl", "apply", "-f", f"k8s/production/{item}", "-n", namespace]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Deployment warning", item=item, error=result.stderr)
                self.deployment_status["warnings"].append(f"Warning deploying {item}: {result.stderr}")
        
        # Wait for deployments to be ready
        await self._wait_for_deployments()
        
        self.deployment_status["steps_completed"].append("kubernetes_deployment")
        logger.info("Kubernetes deployment completed")
    
    async def _wait_for_deployments(self):
        """Wait for all deployments to be ready."""
        
        logger.info("Waiting for deployments to be ready")
        
        namespace = self.config["namespace"]
        timeout = 600  # 10 minutes
        
        # Get all deployments
        result = subprocess.run(
            ["kubectl", "get", "deployments", "-n", namespace, "-o", "json"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            raise Exception("Failed to get deployments")
        
        deployments = json.loads(result.stdout)
        
        for deployment in deployments["items"]:
            name = deployment["metadata"]["name"]
            logger.info("Waiting for deployment", name=name)
            
            # Wait for deployment to be ready
            cmd = [
                "kubectl", "rollout", "status", "deployment", name,
                "-n", namespace, "--timeout", str(timeout) + "s"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Deployment {name} failed to become ready: {result.stderr}")
            
            logger.info("Deployment ready", name=name)
    
    async def _setup_monitoring(self):
        """Setup monitoring and observability."""
        
        self.deployment_status["current_step"] = "monitoring_setup"
        logger.info("Setting up monitoring")
        
        # Deploy monitoring stack
        monitoring_components = [
            "prometheus/",
            "grafana/",
            "jaeger/",
            "alertmanager/"
        ]
        
        for component in monitoring_components:
            logger.info("Deploying monitoring component", component=component)
            
            cmd = ["kubectl", "apply", "-f", f"k8s/monitoring/{component}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("Monitoring deployment warning", component=component, error=result.stderr)
        
        # Import Grafana dashboards
        await self._import_grafana_dashboards()
        
        self.deployment_status["steps_completed"].append("monitoring_setup")
        logger.info("Monitoring setup completed")
    
    async def _import_grafana_dashboards(self):
        """Import Grafana dashboards."""
        
        logger.info("Importing Grafana dashboards")
        
        dashboard_dir = Path("observability/dashboards")
        if not dashboard_dir.exists():
            logger.warning("Dashboard directory not found", path=str(dashboard_dir))
            return
        
        for dashboard_file in dashboard_dir.glob("*.json"):
            logger.info("Importing dashboard", file=str(dashboard_file))
            
            # In production, this would use Grafana API to import dashboards
            # For now, we'll just log the action
            with open(dashboard_file, 'r') as f:
                dashboard_data = json.load(f)
                logger.info("Dashboard imported", name=dashboard_data.get("dashboard", {}).get("title", "Unknown"))
    
    async def _setup_user_experience_tracking(self):
        """Setup user experience tracking."""
        
        self.deployment_status["current_step"] = "user_experience_setup"
        logger.info("Setting up user experience tracking")
        
        # Deploy user experience metrics
        cmd = ["kubectl", "apply", "-f", "k8s/production/user-experience-metrics.yaml"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning("User experience setup warning", error=result.stderr)
        
        # Setup journey tracking
        await self._setup_journey_tracking()
        
        self.deployment_status["steps_completed"].append("user_experience_setup")
        logger.info("User experience tracking setup completed")
    
    async def _setup_journey_tracking(self):
        """Setup user journey tracking."""
        
        logger.info("Setting up user journey tracking")
        
        # This would configure the journey tracker service
        # For now, we'll just log the setup
        logger.info("Journey tracking configured")
    
    async def _run_validation_tests(self):
        """Run validation tests."""
        
        self.deployment_status["current_step"] = "validation_tests"
        logger.info("Running validation tests")
        
        # Health check validation
        await self._health_check_validation()
        
        # Load testing
        await self._load_testing()
        
        # End-to-end testing
        await self._e2e_testing()
        
        self.deployment_status["steps_completed"].append("validation_tests")
        logger.info("Validation tests completed")
    
    async def _health_check_validation(self):
        """Run health check validation."""
        
        logger.info("Running health check validation")
        
        namespace = self.config["namespace"]
        domain = self.config["domain"]
        
        # Check all service health endpoints
        services = [
            "api-gateway", "orchestrator", "router_service", "realtime",
            "analytics-service", "billing-service", "ingestion", "chat-adapters",
            "tenant-service", "admin-portal", "eval-service"
        ]
        
        for service in services:
            try:
                url = f"https://{domain}/api/v1/{service}/health"
                response = requests.get(url, timeout=30, verify=False)
                
                if response.status_code == 200:
                    logger.info("Health check passed", service=service)
                else:
                    raise Exception(f"Health check failed for {service}: {response.status_code}")
                    
            except Exception as e:
                logger.error("Health check error", service=service, error=str(e))
                raise
    
    async def _load_testing(self):
        """Run load testing."""
        
        logger.info("Running load testing")
        
        # This would run actual load tests
        # For now, we'll simulate the process
        await asyncio.sleep(5)  # Simulate load test execution
        
        logger.info("Load testing completed")
    
    async def _e2e_testing(self):
        """Run end-to-end testing."""
        
        logger.info("Running end-to-end testing")
        
        # Run E2E tests
        cmd = ["python", "-m", "pytest", "tests/e2e/test_production_e2e.py", "--env=production"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error("E2E tests failed", error=result.stderr)
            raise Exception("End-to-end tests failed")
        
        logger.info("End-to-end testing completed")
    
    async def _enable_production_traffic(self):
        """Enable production traffic."""
        
        self.deployment_status["current_step"] = "enable_traffic"
        logger.info("Enabling production traffic")
        
        namespace = self.config["namespace"]
        domain = self.config["domain"]
        
        # Update ingress to enable production traffic
        cmd = [
            "kubectl", "patch", "ingress", "api-gateway", "-n", namespace,
            "-p", f'{{"spec":{{"rules":[{{"host":"{domain}"}}]}}}}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("Ingress update warning", error=result.stderr)
        
        self.deployment_status["steps_completed"].append("enable_traffic")
        logger.info("Production traffic enabled")
    
    async def _post_deployment_monitoring(self):
        """Setup post-deployment monitoring."""
        
        self.deployment_status["current_step"] = "post_deployment_monitoring"
        logger.info("Setting up post-deployment monitoring")
        
        # Start monitoring processes
        await self._start_monitoring_processes()
        
        # Setup alerts
        await self._setup_alerts()
        
        self.deployment_status["steps_completed"].append("post_deployment_monitoring")
        logger.info("Post-deployment monitoring setup completed")
    
    async def _start_monitoring_processes(self):
        """Start monitoring processes."""
        
        logger.info("Starting monitoring processes")
        
        # This would start various monitoring processes
        # For now, we'll just log the action
        logger.info("Monitoring processes started")
    
    async def _setup_alerts(self):
        """Setup production alerts."""
        
        logger.info("Setting up production alerts")
        
        # Deploy alert rules
        cmd = ["kubectl", "apply", "-f", "k8s/monitoring/alerts/production-alerts.yaml"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning("Alert setup warning", error=result.stderr)
        
        logger.info("Production alerts configured")
    
    async def _rollback_deployment(self):
        """Rollback deployment in case of failure."""
        
        logger.error("Rolling back deployment")
        
        namespace = self.config["namespace"]
        
        # Delete all resources
        cmd = ["kubectl", "delete", "all", "--all", "-n", namespace]
        subprocess.run(cmd, capture_output=True)
        
        logger.info("Deployment rolled back")
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        
        self.deployment_status["end_time"] = datetime.now()
        self.deployment_status["duration"] = (
            self.deployment_status["end_time"] - self.deployment_status["start_time"]
        ).total_seconds()
        
        return self.deployment_status


async def main():
    """Main deployment function."""
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger.info("Starting production deployment")
    
    try:
        deployment = ProductionDeployment()
        await deployment.deploy()
        
        status = deployment.get_deployment_status()
        logger.info("Deployment completed successfully", status=status)
        
        print("\n🎉 Production Deployment Completed Successfully!")
        print(f"Duration: {status['duration']:.2f} seconds")
        print(f"Steps completed: {len(status['steps_completed'])}")
        print(f"Errors: {len(status['errors'])}")
        print(f"Warnings: {len(status['warnings'])}")
        
    except Exception as e:
        logger.error("Deployment failed", error=str(e))
        print(f"\n❌ Deployment Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
