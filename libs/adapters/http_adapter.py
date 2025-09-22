"""HTTP tool adapter with resilience patterns."""

import httpx
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
import structlog

from src.base_adapter import BaseToolAdapter, AdapterConfig

logger = structlog.get_logger(__name__)


@dataclass
class HTTPAdapterConfig(AdapterConfig):
    """Configuration for HTTP adapter."""

    base_url: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    headers: Dict[str, str] = None
    verify_ssl: bool = True

    def __post_init__(self):
        super().__post_init__()
        if self.headers is None:
            self.headers = {}


class HTTPAdapter(BaseToolAdapter):
    """HTTP tool adapter with resilience patterns."""

    def __init__(self, name: str, config: HTTPAdapterConfig = None):
        self.config = config or HTTPAdapterConfig()
        super().__init__(name, self.config)

        # Create HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=self.config.headers,
            verify=self.config.verify_ssl,
        )

    async def _execute_tool(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request."""
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {e}")
            raise

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request."""
        return await self.execute("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request."""
        return await self.execute("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """PUT request."""
        return await self.execute("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE request."""
        return await self.execute("DELETE", url, **kwargs)

    async def _health_check(self) -> bool:
        """Health check for HTTP adapter."""
        try:
            # Try to make a simple request to check connectivity
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code < 500
        except Exception:
            # If health endpoint doesn't exist, try the base URL
            try:
                response = await self.client.get("/", timeout=5.0)
                return response.status_code < 500
            except Exception:
                return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def stop(self):
        """Stop the adapter and close HTTP client."""
        await super().stop()
        await self.close()
