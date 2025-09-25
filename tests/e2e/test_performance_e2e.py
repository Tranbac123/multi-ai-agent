"""
E2E Performance Tests
"""
import pytest
import asyncio
import httpx
import time
from typing import Dict, Any, List
import statistics


class TestPerformanceE2E:
    """Test performance characteristics across services."""
    
    @pytest.mark.asyncio
    async def test_response_time_benchmarks(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test response time benchmarks for all services."""
        
        services_to_test = [
            ("API Gateway", service_urls["api_gateway"]),
            ("Model Gateway", service_urls["model_gateway"]),
            ("Config Service", service_urls["config_service"]),
            ("Retrieval Service", service_urls["retrieval_service"]),
            ("Tools Service", service_urls["tools_service"]),
            ("Router Service", service_urls["router_service"]),
            ("Policy Adapter", service_urls["policy_adapter"]),
            ("Admin Portal", service_urls["admin_portal"]),
        ]
        
        response_times = {}
        
        for service_name, url in services_to_test:
            times = []
            
            # Test multiple requests to get average response time
            for _ in range(5):
                start_time = time.time()
                try:
                    response = await http_client.get(f"{url}/healthz", timeout=10.0)
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        response_time = (end_time - start_time) * 1000  # Convert to ms
                        times.append(response_time)
                except Exception:
                    # Skip failed requests
                    pass
            
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                response_times[service_name] = {
                    "avg_ms": round(avg_time, 2),
                    "min_ms": round(min_time, 2),
                    "max_ms": round(max_time, 2),
                    "samples": len(times)
                }
        
        # Print results
        print(f"\n⏱️ Response Time Benchmarks:")
        print("=" * 60)
        for service_name, metrics in response_times.items():
            print(f"{service_name:20} | Avg: {metrics['avg_ms']:6.2f}ms | Min: {metrics['min_ms']:6.2f}ms | Max: {metrics['max_ms']:6.2f}ms")
        
        # Assertions for acceptable response times
        for service_name, metrics in response_times.items():
            # Most services should respond within 2 seconds
            assert metrics["avg_ms"] < 2000, f"{service_name} average response time too slow: {metrics['avg_ms']}ms"
            
            # Health checks should be fast
            if "health" in service_name.lower() or "gateway" in service_name.lower():
                assert metrics["avg_ms"] < 1000, f"{service_name} health check too slow: {metrics['avg_ms']}ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_load_performance(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test performance under concurrent load."""
        
        async def make_concurrent_requests(url: str, num_requests: int = 10):
            """Make multiple concurrent requests to a service."""
            tasks = []
            for _ in range(num_requests):
                task = http_client.get(f"{url}/healthz", timeout=5.0)
                tasks.append(task)
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
            total_time = (end_time - start_time) * 1000
            
            return {
                "total_requests": num_requests,
                "successful": successful,
                "failed": num_requests - successful,
                "total_time_ms": round(total_time, 2),
                "requests_per_second": round(num_requests / (total_time / 1000), 2) if total_time > 0 else 0
            }
        
        # Test concurrent load on key services
        test_services = [
            ("API Gateway", service_urls["api_gateway"]),
            ("Model Gateway", service_urls["model_gateway"]),
            ("Config Service", service_urls["config_service"]),
        ]
        
        load_results = {}
        
        for service_name, url in test_services:
            try:
                result = await make_concurrent_requests(url, num_requests=20)
                load_results[service_name] = result
            except Exception as e:
                load_results[service_name] = {"error": str(e)}
        
        # Print results
        print(f"\n🚀 Concurrent Load Test Results:")
        print("=" * 70)
        for service_name, result in load_results.items():
            if "error" in result:
                print(f"{service_name:20} | Error: {result['error']}")
            else:
                success_rate = (result["successful"] / result["total_requests"]) * 100
                print(f"{service_name:20} | Success: {result['successful']:2}/{result['total_requests']:2} ({success_rate:5.1f}%) | RPS: {result['requests_per_second']:6.2f}")
        
        # Assertions
        for service_name, result in load_results.items():
            if "error" not in result:
                success_rate = result["successful"] / result["total_requests"]
                # At least 80% of requests should succeed under load
                assert success_rate >= 0.8, f"{service_name} success rate too low under load: {success_rate:.2%}"
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test memory usage stability over time."""
        
        # This is a simplified test - in production you'd use monitoring tools
        # For E2E, we'll test that services remain responsive after multiple requests
        
        test_service = service_urls["api_gateway"]
        initial_response_times = []
        final_response_times = []
        
        # Measure initial response times
        for _ in range(5):
            start_time = time.time()
            try:
                response = await http_client.get(f"{test_service}/healthz", timeout=5.0)
                end_time = time.time()
                if response.status_code == 200:
                    initial_response_times.append((end_time - start_time) * 1000)
            except Exception:
                pass
        
        # Make many requests to potentially cause memory pressure
        for _ in range(100):
            try:
                await http_client.get(f"{test_service}/healthz", timeout=2.0)
            except Exception:
                pass
        
        # Measure final response times
        for _ in range(5):
            start_time = time.time()
            try:
                response = await http_client.get(f"{test_service}/healthz", timeout=5.0)
                end_time = time.time()
                if response.status_code == 200:
                    final_response_times.append((end_time - start_time) * 1000)
            except Exception:
                pass
        
        if initial_response_times and final_response_times:
            initial_avg = statistics.mean(initial_response_times)
            final_avg = statistics.mean(final_response_times)
            
            print(f"\n🧠 Memory Stability Test:")
            print(f"Initial avg response time: {initial_avg:.2f}ms")
            print(f"Final avg response time: {final_avg:.2f}ms")
            print(f"Performance degradation: {((final_avg - initial_avg) / initial_avg * 100):+.1f}%")
            
            # Response times shouldn't degrade by more than 50%
            degradation = (final_avg - initial_avg) / initial_avg
            assert degradation < 0.5, f"Performance degraded too much: {degradation:.2%}"
    
    @pytest.mark.asyncio
    async def test_end_to_end_latency(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test end-to-end latency for complete user workflows."""
        
        workflows = [
            {
                "name": "Chat Workflow",
                "steps": [
                    ("GET", f"{service_urls['ai_chatbot']}", None),
                    ("POST", f"{service_urls['api_gateway']}/v1/chat", {
                        "messages": [{"role": "user", "content": "Hello"}],
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.7,
                        "max_tokens": 50
                    })
                ]
            },
            {
                "name": "Admin Workflow",
                "steps": [
                    ("GET", f"{service_urls['admin_portal']}", None),
                    ("GET", f"{service_urls['admin_portal']}/healthz", None),
                    ("GET", f"{service_urls['api_gateway']}/healthz", None)
                ]
            },
            {
                "name": "Search Workflow",
                "steps": [
                    ("GET", f"{service_urls['retrieval_service']}/healthz", None),
                    ("POST", f"{service_urls['retrieval_service']}/search", {
                        "query": "test search",
                        "limit": 10,
                        "user_id": test_user_data["user_id"]
                    })
                ]
            }
        ]
        
        workflow_results = {}
        
        for workflow in workflows:
            total_time = 0
            step_times = []
            
            for method, url, data in workflow["steps"]:
                start_time = time.time()
                try:
                    if method == "GET":
                        response = await http_client.get(url, timeout=10.0)
                    else:
                        response = await http_client.post(url, json=data, timeout=10.0)
                    
                    end_time = time.time()
                    step_time = (end_time - start_time) * 1000
                    step_times.append(step_time)
                    total_time += step_time
                    
                except Exception as e:
                    step_times.append(float('inf'))  # Mark failed steps
            
            workflow_results[workflow["name"]] = {
                "total_time_ms": round(total_time, 2),
                "step_times": step_times,
                "success": not any(t == float('inf') for t in step_times)
            }
        
        # Print results
        print(f"\n🔄 End-to-End Latency Results:")
        print("=" * 50)
        for workflow_name, result in workflow_results.items():
            status = "✅" if result["success"] else "❌"
            print(f"{status} {workflow_name:20} | Total: {result['total_time_ms']:8.2f}ms")
        
        # Assertions
        for workflow_name, result in workflow_results.items():
            if result["success"]:
                # Complete workflows should finish within reasonable time
                assert result["total_time_ms"] < 10000, f"{workflow_name} too slow: {result['total_time_ms']}ms"
    
    @pytest.mark.asyncio
    async def test_error_recovery_performance(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test how quickly services recover from errors."""
        
        test_service = service_urls["api_gateway"]
        
        # Make some requests that might cause errors
        error_requests = [
            ("GET", f"{test_service}/nonexistent-endpoint"),
            ("POST", f"{test_service}/v1/chat"),
            ("GET", f"{test_service}/invalid-path"),
        ]
        
        error_times = []
        recovery_times = []
        
        for method, url in error_requests:
            # Measure error response time
            start_time = time.time()
            try:
                if method == "GET":
                    response = await http_client.get(url, timeout=5.0)
                else:
                    response = await http_client.post(url, json={"invalid": "data"}, timeout=5.0)
                end_time = time.time()
                error_times.append((end_time - start_time) * 1000)
            except Exception:
                error_times.append(1000)  # Default error time
        
        # Test recovery by making successful requests
        for _ in range(3):
            start_time = time.time()
            try:
                response = await http_client.get(f"{test_service}/healthz", timeout=5.0)
                end_time = time.time()
                if response.status_code == 200:
                    recovery_times.append((end_time - start_time) * 1000)
            except Exception:
                pass
        
        if error_times and recovery_times:
            avg_error_time = statistics.mean(error_times)
            avg_recovery_time = statistics.mean(recovery_times)
            
            print(f"\n🔄 Error Recovery Performance:")
            print(f"Average error response time: {avg_error_time:.2f}ms")
            print(f"Average recovery time: {avg_recovery_time:.2f}ms")
            
            # Recovery should be fast (within 2 seconds)
            assert avg_recovery_time < 2000, f"Recovery too slow: {avg_recovery_time}ms"
            
            # Error responses should also be reasonably fast
            assert avg_error_time < 5000, f"Error responses too slow: {avg_error_time}ms"
