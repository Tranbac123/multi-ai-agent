"""Request Hedging Manager for reducing tail latency through coordinated cancellation."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import uuid
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class HedgingStrategy(Enum):
    """Request hedging strategies."""
    PARALLEL = "parallel"  # Send all requests in parallel
    STAGGERED = "staggered"  # Send requests with delays
    ADAPTIVE = "adaptive"  # Adaptive based on latency history


class HedgingResult(Enum):
    """Hedging result types."""
    FIRST_WIN = "first_win"
    HEDGE_WIN = "hedge_win"
    CANCELLED = "cancelled"
    ALL_FAILED = "all_failed"


@dataclass
class HedgingConfig:
    """Configuration for request hedging."""
    max_parallel_requests: int = 2
    hedge_delay_ms: int = 50  # Delay before sending hedge request
    timeout_ms: int = 5000
    cancel_others_on_first_success: bool = True
    strategy: HedgingStrategy = HedgingStrategy.STAGGERED
    max_cost_multiplier: float = 1.5  # Max cost increase from hedging


@dataclass
class HedgingRequest:
    """Individual hedging request."""
    request_id: str
    url: str
    method: str
    headers: Dict[str, str]
    data: Optional[Any]
    timeout: float
    created_at: datetime
    cancelled: bool = False


@dataclass
class HedgingResponse:
    """Response from hedging request."""
    request_id: str
    status_code: int
    data: Any
    latency_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class HedgingResult:
    """Result of hedging operation."""
    result_type: HedgingResult
    winning_response: Optional[HedgingResponse]
    all_responses: List[HedgingResponse]
    total_latency_ms: float
    cost_multiplier: float
    hedged_requests_count: int


class RequestHedgingManager:
    """Manages request hedging for reducing tail latency."""
    
    def __init__(self, http_client_factory: Callable = None):
        self.http_client_factory = http_client_factory
        self.hedging_config = HedgingConfig()
        self.active_requests: Dict[str, List[HedgingRequest]] = {}
        self.hedging_stats = {
            "total_hedged_requests": 0,
            "first_wins": 0,
            "hedge_wins": 0,
            "cancelled_requests": 0,
            "all_failed": 0,
            "total_cost_savings": 0.0
        }
    
    async def hedge_request(self, urls: List[str], method: str = "GET", 
                          headers: Optional[Dict[str, str]] = None,
                          data: Optional[Any] = None,
                          timeout: Optional[float] = None) -> HedgingResult:
        """Execute hedged request across multiple URLs."""
        try:
            hedging_id = str(uuid.uuid4())
            start_time = time.time()
            
            logger.info("Starting hedged request",
                       hedging_id=hedging_id,
                       urls=urls,
                       strategy=self.hedging_config.strategy.value)
            
            # Create hedging requests
            hedging_requests = self._create_hedging_requests(
                hedging_id, urls, method, headers, data, timeout
            )
            
            # Store active requests
            self.active_requests[hedging_id] = hedging_requests
            
            # Execute hedging based on strategy
            if self.hedging_config.strategy == HedgingStrategy.PARALLEL:
                result = await self._execute_parallel_hedging(hedging_requests)
            elif self.hedging_config.strategy == HedgingStrategy.STAGGERED:
                result = await self._execute_staggered_hedging(hedging_requests)
            else:  # ADAPTIVE
                result = await self._execute_adaptive_hedging(hedging_requests)
            
            # Calculate final metrics
            total_latency = (time.time() - start_time) * 1000
            result.total_latency_ms = total_latency
            result.hedged_requests_count = len(hedging_requests)
            result.cost_multiplier = len(hedging_requests)
            
            # Update statistics
            self._update_hedging_stats(result)
            
            # Cleanup
            del self.active_requests[hedging_id]
            
            logger.info("Hedged request completed",
                       hedging_id=hedging_id,
                       result_type=result.result_type.value,
                       total_latency_ms=total_latency,
                       cost_multiplier=result.cost_multiplier)
            
            return result
            
        except Exception as e:
            logger.error("Hedged request failed", hedging_id=hedging_id, error=str(e))
            return HedgingResult(
                result_type=HedgingResult.ALL_FAILED,
                winning_response=None,
                all_responses=[],
                total_latency_ms=0.0,
                cost_multiplier=1.0,
                hedged_requests_count=0
            )
    
    def _create_hedging_requests(self, hedging_id: str, urls: List[str], 
                               method: str, headers: Optional[Dict[str, str]], 
                               data: Optional[Any], timeout: Optional[float]) -> List[HedgingRequest]:
        """Create hedging requests for each URL."""
        requests = []
        
        for i, url in enumerate(urls):
            request_id = f"{hedging_id}_{i}"
            request_timeout = timeout or (self.hedging_config.timeout_ms / 1000.0)
            
            request = HedgingRequest(
                request_id=request_id,
                url=url,
                method=method,
                headers=headers or {},
                data=data,
                timeout=request_timeout,
                created_at=datetime.now(timezone.utc)
            )
            
            requests.append(request)
        
        return requests
    
    async def _execute_parallel_hedging(self, requests: List[HedgingRequest]) -> HedgingResult:
        """Execute all requests in parallel."""
        try:
            # Create tasks for all requests
            tasks = []
            for request in requests:
                task = asyncio.create_task(self._execute_single_request(request))
                tasks.append(task)
            
            # Wait for first successful response or all to complete
            if self.hedging_config.cancel_others_on_first_success:
                # Use as_completed to get first successful result
                responses = []
                first_success = None
                
                for task in asyncio.as_completed(tasks):
                    try:
                        response = await task
                        responses.append(response)
                        
                        if response.success and first_success is None:
                            first_success = response
                            # Cancel remaining tasks
                            for remaining_task in tasks:
                                if not remaining_task.done():
                                    remaining_task.cancel()
                            break
                    except Exception as e:
                        logger.error("Task failed in parallel hedging", error=str(e))
                        responses.append(HedgingResponse(
                            request_id="failed",
                            status_code=500,
                            data=None,
                            latency_ms=0.0,
                            success=False,
                            error=str(e)
                        ))
                
                # Wait for cancellation to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                if first_success:
                    return HedgingResult(
                        result_type=HedgingResult.FIRST_WIN,
                        winning_response=first_success,
                        all_responses=responses,
                        total_latency_ms=0.0,  # Will be set by caller
                        cost_multiplier=len(requests),
                        hedged_requests_count=len(requests)
                    )
                else:
                    return HedgingResult(
                        result_type=HedgingResult.ALL_FAILED,
                        winning_response=None,
                        all_responses=responses,
                        total_latency_ms=0.0,
                        cost_multiplier=len(requests),
                        hedged_requests_count=len(requests)
                    )
            else:
                # Wait for all to complete
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Find first successful response
                first_success = None
                for response in responses:
                    if isinstance(response, HedgingResponse) and response.success:
                        first_success = response
                        break
                
                if first_success:
                    return HedgingResult(
                        result_type=HedgingResult.FIRST_WIN,
                        winning_response=first_success,
                        all_responses=responses,
                        total_latency_ms=0.0,
                        cost_multiplier=len(requests),
                        hedged_requests_count=len(requests)
                    )
                else:
                    return HedgingResult(
                        result_type=HedgingResult.ALL_FAILED,
                        winning_response=None,
                        all_responses=responses,
                        total_latency_ms=0.0,
                        cost_multiplier=len(requests),
                        hedged_requests_count=len(requests)
                    )
                    
        except Exception as e:
            logger.error("Parallel hedging failed", error=str(e))
            return HedgingResult(
                result_type=HedgingResult.ALL_FAILED,
                winning_response=None,
                all_responses=[],
                total_latency_ms=0.0,
                cost_multiplier=len(requests),
                hedged_requests_count=len(requests)
            )
    
    async def _execute_staggered_hedging(self, requests: List[HedgingRequest]) -> HedgingResult:
        """Execute requests with staggered delays."""
        try:
            responses = []
            winning_response = None
            result_type = HedgingResult.ALL_FAILED
            
            for i, request in enumerate(requests):
                # Add delay for hedge requests
                if i > 0:
                    delay = self.hedging_config.hedge_delay_ms / 1000.0
                    await asyncio.sleep(delay)
                
                # Check if we already have a successful response
                if winning_response and self.hedging_config.cancel_others_on_first_success:
                    request.cancelled = True
                    responses.append(HedgingResponse(
                        request_id=request.request_id,
                        status_code=0,
                        data=None,
                        latency_ms=0.0,
                        success=False,
                        error="Cancelled due to earlier success"
                    ))
                    continue
                
                # Execute request
                response = await self._execute_single_request(request)
                responses.append(response)
                
                # Check if this is the first successful response
                if response.success and winning_response is None:
                    winning_response = response
                    result_type = HedgingResult.FIRST_WIN if i == 0 else HedgingResult.HEDGE_WIN
            
            return HedgingResult(
                result_type=result_type,
                winning_response=winning_response,
                all_responses=responses,
                total_latency_ms=0.0,
                cost_multiplier=len(requests),
                hedged_requests_count=len(requests)
            )
            
        except Exception as e:
            logger.error("Staggered hedging failed", error=str(e))
            return HedgingResult(
                result_type=HedgingResult.ALL_FAILED,
                winning_response=None,
                all_responses=responses,
                total_latency_ms=0.0,
                cost_multiplier=len(requests),
                hedged_requests_count=len(requests)
            )
    
    async def _execute_adaptive_hedging(self, requests: List[HedgingRequest]) -> HedgingResult:
        """Execute adaptive hedging based on historical performance."""
        try:
            # For now, implement as staggered hedging
            # In production, this would analyze historical latency data
            # to determine optimal hedging strategy
            
            return await self._execute_staggered_hedging(requests)
            
        except Exception as e:
            logger.error("Adaptive hedging failed", error=str(e))
            return HedgingResult(
                result_type=HedgingResult.ALL_FAILED,
                winning_response=None,
                all_responses=[],
                total_latency_ms=0.0,
                cost_multiplier=len(requests),
                hedged_requests_count=len(requests)
            )
    
    async def _execute_single_request(self, request: HedgingRequest) -> HedgingResponse:
        """Execute a single HTTP request."""
        try:
            start_time = time.time()
            
            # Create HTTP client
            if self.http_client_factory:
                async with self.http_client_factory() as client:
                    response = await client.request(
                        method=request.method,
                        url=request.url,
                        headers=request.headers,
                        data=request.data,
                        timeout=request.timeout
                    )
            else:
                # Default implementation using aiohttp
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=request.method,
                        url=request.url,
                        headers=request.headers,
                        data=request.data,
                        timeout=aiohttp.ClientTimeout(total=request.timeout)
                    ) as response:
                        response_data = await response.text()
            
            latency = (time.time() - start_time) * 1000
            
            return HedgingResponse(
                request_id=request.request_id,
                status_code=response.status,
                data=response_data,
                latency_ms=latency,
                success=200 <= response.status < 300,
                error=None
            )
            
        except asyncio.TimeoutError:
            return HedgingResponse(
                request_id=request.request_id,
                status_code=408,
                data=None,
                latency_ms=request.timeout * 1000,
                success=False,
                error="Request timeout"
            )
        except Exception as e:
            return HedgingResponse(
                request_id=request.request_id,
                status_code=500,
                data=None,
                latency_ms=0.0,
                success=False,
                error=str(e)
            )
    
    def _update_hedging_stats(self, result: HedgingResult):
        """Update hedging statistics."""
        try:
            self.hedging_stats["total_hedged_requests"] += 1
            
            if result.result_type == HedgingResult.FIRST_WIN:
                self.hedging_stats["first_wins"] += 1
            elif result.result_type == HedgingResult.HEDGE_WIN:
                self.hedging_stats["hedge_wins"] += 1
            elif result.result_type == HedgingResult.CANCELLED:
                self.hedging_stats["cancelled_requests"] += 1
            elif result.result_type == HedgingResult.ALL_FAILED:
                self.hedging_stats["all_failed"] += 1
            
            # Calculate cost savings (simplified)
            if result.winning_response:
                # Estimate cost savings from reduced latency
                estimated_savings = result.winning_response.latency_ms * 0.001  # $0.001 per ms
                self.hedging_stats["total_cost_savings"] += estimated_savings
            
        except Exception as e:
            logger.error("Failed to update hedging stats", error=str(e))
    
    def get_hedging_stats(self) -> Dict[str, Any]:
        """Get hedging statistics."""
        try:
            total = self.hedging_stats["total_hedged_requests"]
            
            stats = {
                "total_hedged_requests": total,
                "first_wins": self.hedging_stats["first_wins"],
                "hedge_wins": self.hedging_stats["hedge_wins"],
                "cancelled_requests": self.hedging_stats["cancelled_requests"],
                "all_failed": self.hedging_stats["all_failed"],
                "total_cost_savings": self.hedging_stats["total_cost_savings"],
                "first_win_rate": (
                    self.hedging_stats["first_wins"] / total * 100
                ) if total > 0 else 0,
                "hedge_win_rate": (
                    self.hedging_stats["hedge_wins"] / total * 100
                ) if total > 0 else 0,
                "success_rate": (
                    (self.hedging_stats["first_wins"] + self.hedging_stats["hedge_wins"]) / total * 100
                ) if total > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get hedging stats", error=str(e))
            return {}
    
    def update_hedging_config(self, config: HedgingConfig):
        """Update hedging configuration."""
        self.hedging_config = config
        logger.info("Hedging configuration updated",
                   strategy=config.strategy.value,
                   max_parallel=config.max_parallel_requests,
                   hedge_delay_ms=config.hedge_delay_ms,
                   timeout_ms=config.timeout_ms)
    
    async def cancel_hedging_request(self, hedging_id: str) -> bool:
        """Cancel an active hedging request."""
        try:
            if hedging_id in self.active_requests:
                requests = self.active_requests[hedging_id]
                
                for request in requests:
                    request.cancelled = True
                
                del self.active_requests[hedging_id]
                
                logger.info("Hedging request cancelled", hedging_id=hedging_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to cancel hedging request",
                        hedging_id=hedging_id,
                        error=str(e))
            return False
