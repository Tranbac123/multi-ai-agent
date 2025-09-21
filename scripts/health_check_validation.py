#!/usr/bin/env python3
"""
Health Check Validation Script for Production Deployment

This script validates the health of all services after deployment
to ensure they are ready for production traffic.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog
import requests
import subprocess
from urllib.parse import urljoin

logger = structlog.get_logger(__name__)


class HealthCheckValidator:
    """Health check validator for production deployment."""
    
    def __init__(self, namespace: str, domain: str, timeout: int = 30):
        self.namespace = namespace
        self.domain = domain
        self.timeout = timeout
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "namespace": namespace,
            "domain": domain,
            "services": {},
            "overall_status": "unknown",
            "summary": {
                "total_services": 0,
                "healthy_services": 0,
                "unhealthy_services": 0,
                "failed_checks": 0
            }
        }
        
    async def validate_all_services(self) -> Dict[str, Any]:
        """Validate health of all services."""
        
        logger.info("Starting health check validation", 
                   namespace=self.namespace, domain=self.domain)
        
        services = [
            "api-gateway",
            "orchestrator", 
            "router_service",
            "realtime-service",
            "analytics-service",
            "billing-service",
            "ingestion",
            "chat-adapters",
            "tenant-service",
            "admin-portal",
            "eval-service"
        ]
        
        self.results["summary"]["total_services"] = len(services)
        
        # Validate each service
        for service in services:
            await self._validate_service(service)
        
        # Calculate overall status
        self._calculate_overall_status()
        
        # Generate report
        self._generate_report()
        
        logger.info("Health check validation completed", 
                   overall_status=self.results["overall_status"],
                   healthy_services=self.results["summary"]["healthy_services"],
                   unhealthy_services=self.results["summary"]["unhealthy_services"])
        
        return self.results
    
    async def _validate_service(self, service: str):
        """Validate health of a specific service."""
        
        logger.info("Validating service", service=service)
        
        service_result = {
            "service": service,
            "status": "unknown",
            "checks": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Check 1: Kubernetes deployment status
            deployment_status = await self._check_deployment_status(service)
            service_result["checks"]["deployment"] = deployment_status
            
            # Check 2: Pod health
            pod_status = await self._check_pod_health(service)
            service_result["checks"]["pods"] = pod_status
            
            # Check 3: Service endpoint health
            endpoint_status = await self._check_endpoint_health(service)
            service_result["checks"]["endpoint"] = endpoint_status
            
            # Check 4: Service connectivity
            connectivity_status = await self._check_service_connectivity(service)
            service_result["checks"]["connectivity"] = connectivity_status
            
            # Check 5: Resource utilization
            resource_status = await self._check_resource_utilization(service)
            service_result["checks"]["resources"] = resource_status
            
            # Determine overall service status
            service_result["status"] = self._determine_service_status(service_result["checks"])
            
            if service_result["status"] == "healthy":
                self.results["summary"]["healthy_services"] += 1
            else:
                self.results["summary"]["unhealthy_services"] += 1
                self.results["summary"]["failed_checks"] += 1
            
        except Exception as e:
            logger.error("Error validating service", service=service, error=str(e))
            service_result["status"] = "error"
            service_result["error"] = str(e)
            self.results["summary"]["unhealthy_services"] += 1
            self.results["summary"]["failed_checks"] += 1
        
        self.results["services"][service] = service_result
    
    async def _check_deployment_status(self, service: str) -> Dict[str, Any]:
        """Check Kubernetes deployment status."""
        
        try:
            cmd = [
                "kubectl", "get", "deployment", service,
                "-n", self.namespace, "-o", "json"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {
                    "status": "failed",
                    "error": f"Failed to get deployment status: {result.stderr}"
                }
            
            deployment_data = json.loads(result.stdout)
            
            status = deployment_data.get("status", {})
            spec = deployment_data.get("spec", {})
            
            desired_replicas = spec.get("replicas", 0)
            ready_replicas = status.get("readyReplicas", 0)
            available_replicas = status.get("availableReplicas", 0)
            updated_replicas = status.get("updatedReplicas", 0)
            
            is_ready = (
                ready_replicas == desired_replicas and
                available_replicas == desired_replicas and
                updated_replicas == desired_replicas
            )
            
            return {
                "status": "healthy" if is_ready else "unhealthy",
                "desired_replicas": desired_replicas,
                "ready_replicas": ready_replicas,
                "available_replicas": available_replicas,
                "updated_replicas": updated_replicas,
                "is_ready": is_ready
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_pod_health(self, service: str) -> Dict[str, Any]:
        """Check pod health status."""
        
        try:
            cmd = [
                "kubectl", "get", "pods", "-l", f"app={service}",
                "-n", self.namespace, "-o", "json"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {
                    "status": "failed",
                    "error": f"Failed to get pod status: {result.stderr}"
                }
            
            pods_data = json.loads(result.stdout)
            pods = pods_data.get("items", [])
            
            if not pods:
                return {
                    "status": "unhealthy",
                    "error": "No pods found for service"
                }
            
            total_pods = len(pods)
            running_pods = 0
            failed_pods = 0
            pending_pods = 0
            
            pod_details = []
            
            for pod in pods:
                pod_name = pod.get("metadata", {}).get("name", "unknown")
                pod_status = pod.get("status", {})
                phase = pod_status.get("phase", "Unknown")
                
                pod_detail = {
                    "name": pod_name,
                    "phase": phase,
                    "ready": False
                }
                
                # Check if pod is ready
                conditions = pod_status.get("conditions", [])
                for condition in conditions:
                    if condition.get("type") == "Ready":
                        pod_detail["ready"] = condition.get("status") == "True"
                        break
                
                if phase == "Running" and pod_detail["ready"]:
                    running_pods += 1
                elif phase == "Failed":
                    failed_pods += 1
                elif phase == "Pending":
                    pending_pods += 1
                
                pod_details.append(pod_detail)
            
            is_healthy = running_pods == total_pods and failed_pods == 0
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "total_pods": total_pods,
                "running_pods": running_pods,
                "failed_pods": failed_pods,
                "pending_pods": pending_pods,
                "pod_details": pod_details
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_endpoint_health(self, service: str) -> Dict[str, Any]:
        """Check service endpoint health."""
        
        try:
            # Determine health endpoint path
            if service == "api-gateway":
                health_url = f"https://{self.domain}/health"
            else:
                health_url = f"https://{self.domain}/api/v1/{service}/health"
            
            logger.debug("Checking endpoint health", service=service, url=health_url)
            
            response = requests.get(
                health_url,
                timeout=self.timeout,
                verify=False,  # In production, you should use proper SSL verification
                headers={"User-Agent": "HealthCheck/1.0"}
            )
            
            response_time = response.elapsed.total_seconds()
            
            if response.status_code == 200:
                try:
                    health_data = response.json()
                    return {
                        "status": "healthy",
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "health_data": health_data
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "healthy",
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "response_text": response.text[:200]
                    }
            else:
                return {
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "response_text": response.text[:200]
                }
                
        except requests.exceptions.Timeout:
            return {
                "status": "unhealthy",
                "error": f"Request timeout after {self.timeout} seconds"
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "unhealthy",
                "error": "Connection error"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_service_connectivity(self, service: str) -> Dict[str, Any]:
        """Check service internal connectivity."""
        
        try:
            # Check service DNS resolution
            service_name = f"{service}.{self.namespace}.svc.cluster.local"
            
            cmd = ["nslookup", service_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            dns_resolution = result.returncode == 0
            
            # Check service port connectivity
            cmd = [
                "kubectl", "get", "service", service,
                "-n", self.namespace, "-o", "jsonpath={.spec.ports[0].port}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            service_port = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            return {
                "status": "healthy" if dns_resolution else "unhealthy",
                "dns_resolution": dns_resolution,
                "service_port": service_port
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_resource_utilization(self, service: str) -> Dict[str, Any]:
        """Check resource utilization."""
        
        try:
            # Get resource usage
            cmd = [
                "kubectl", "top", "pods", "-l", f"app={service}",
                "-n", self.namespace, "--no-headers"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {
                    "status": "unknown",
                    "error": "Failed to get resource usage"
                }
            
            lines = result.stdout.strip().split('\n')
            pod_usage = []
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        pod_usage.append({
                            "pod": parts[0],
                            "cpu": parts[1],
                            "memory": parts[2]
                        })
            
            return {
                "status": "healthy",
                "pod_usage": pod_usage
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _determine_service_status(self, checks: Dict[str, Any]) -> str:
        """Determine overall service status from individual checks."""
        
        critical_checks = ["deployment", "pods", "endpoint"]
        warning_checks = ["connectivity", "resources"]
        
        critical_failures = 0
        warning_failures = 0
        
        for check_name in critical_checks:
            if check_name in checks:
                check_status = checks[check_name].get("status", "unknown")
                if check_status in ["unhealthy", "error", "failed"]:
                    critical_failures += 1
        
        for check_name in warning_checks:
            if check_name in checks:
                check_status = checks[check_name].get("status", "unknown")
                if check_status in ["unhealthy", "error", "failed"]:
                    warning_failures += 1
        
        if critical_failures > 0:
            return "unhealthy"
        elif warning_failures > 0:
            return "degraded"
        else:
            return "healthy"
    
    def _calculate_overall_status(self):
        """Calculate overall deployment status."""
        
        total_services = self.results["summary"]["total_services"]
        healthy_services = self.results["summary"]["healthy_services"]
        unhealthy_services = self.results["summary"]["unhealthy_services"]
        
        if unhealthy_services == 0:
            self.results["overall_status"] = "healthy"
        elif healthy_services > unhealthy_services:
            self.results["overall_status"] = "degraded"
        else:
            self.results["overall_status"] = "unhealthy"
    
    def _generate_report(self):
        """Generate health check report."""
        
        report = {
            "summary": self.results["summary"],
            "overall_status": self.results["overall_status"],
            "recommendations": []
        }
        
        # Generate recommendations based on findings
        for service, service_result in self.results["services"].items():
            if service_result["status"] != "healthy":
                if service_result["status"] == "unhealthy":
                    report["recommendations"].append(
                        f"Service {service} is unhealthy - investigate deployment and pod status"
                    )
                elif service_result["status"] == "degraded":
                    report["recommendations"].append(
                        f"Service {service} is degraded - check connectivity and resource usage"
                    )
        
        if self.results["summary"]["failed_checks"] > 0:
            report["recommendations"].append(
                f"Multiple health check failures detected ({self.results['summary']['failed_checks']}) - review service logs"
            )
        
        self.results["report"] = report


async def main():
    """Main health check validation function."""
    
    parser = argparse.ArgumentParser(description="Health Check Validation for Production Deployment")
    parser.add_argument("--namespace", default="multi-ai-agent-prod", help="Kubernetes namespace")
    parser.add_argument("--domain", required=True, help="Production domain")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--output", help="Output file for results")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = "DEBUG" if args.verbose else "INFO"
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
    
    logger.info("Starting health check validation", 
               namespace=args.namespace, domain=args.domain)
    
    try:
        validator = HealthCheckValidator(args.namespace, args.domain, args.timeout)
        results = await validator.validate_all_services()
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info("Results saved to file", file=args.output)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Health Check Validation Results")
        print(f"{'='*60}")
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"Namespace: {results['namespace']}")
        print(f"Domain: {results['domain']}")
        print(f"Total Services: {results['summary']['total_services']}")
        print(f"Healthy Services: {results['summary']['healthy_services']}")
        print(f"Unhealthy Services: {results['summary']['unhealthy_services']}")
        print(f"Failed Checks: {results['summary']['failed_checks']}")
        
        if results['summary']['unhealthy_services'] > 0:
            print(f"\nUnhealthy Services:")
            for service, service_result in results['services'].items():
                if service_result['status'] != 'healthy':
                    print(f"  - {service}: {service_result['status']}")
        
        if 'report' in results and results['report']['recommendations']:
            print(f"\nRecommendations:")
            for recommendation in results['report']['recommendations']:
                print(f"  - {recommendation}")
        
        print(f"{'='*60}")
        
        # Exit with appropriate code
        if results['overall_status'] == 'healthy':
            logger.info("Health check validation passed")
            sys.exit(0)
        elif results['overall_status'] == 'degraded':
            logger.warning("Health check validation passed with warnings")
            sys.exit(1)
        else:
            logger.error("Health check validation failed")
            sys.exit(2)
            
    except Exception as e:
        logger.error("Health check validation failed", error=str(e))
        print(f"Health check validation failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
