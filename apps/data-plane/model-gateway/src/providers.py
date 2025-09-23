import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import httpx
from .models import CompletionRequest, CompletionResponse, Usage, Provider
from .settings import settings

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        pass

class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"
        
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": request.stream
        }
        
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
        usage = Usage(
            prompt_tokens=data["usage"]["prompt_tokens"],
            completion_tokens=data["usage"]["completion_tokens"],
            total_tokens=data["usage"]["total_tokens"],
            cost_usd=self.estimate_cost(
                data["usage"]["prompt_tokens"],
                data["usage"]["completion_tokens"],
                request.model
            )
        )
        
        return CompletionResponse(
            id=data["id"],
            model=data["model"],
            provider=Provider.OPENAI,
            content=data["choices"][0]["message"]["content"],
            usage=usage,
            finish_reason=data["choices"][0]["finish_reason"],
            created_at=str(data["created"])
        )
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        # Simplified pricing - should be configurable
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03}
        }
        
        if model not in pricing:
            return 0.0
            
        return (
            (prompt_tokens / 1000) * pricing[model]["prompt"] +
            (completion_tokens / 1000) * pricing[model]["completion"]
        )

class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.base_url = "https://api.anthropic.com/v1"
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")
        
        # Convert messages to Anthropic format
        system_msg = ""
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1000,
            "messages": messages,
            "temperature": request.temperature
        }
        
        if system_msg:
            payload["system"] = system_msg
        
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        # Estimate tokens (Anthropic doesn't always return usage)
        prompt_tokens = data.get("usage", {}).get("input_tokens", 0)
        completion_tokens = data.get("usage", {}).get("output_tokens", 0)
        
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=self.estimate_cost(prompt_tokens, completion_tokens, request.model)
        )
        
        return CompletionResponse(
            id=data.get("id", str(uuid.uuid4())),
            model=data.get("model", request.model),
            provider=Provider.ANTHROPIC,
            content=data["content"][0]["text"],
            usage=usage,
            finish_reason=data.get("stop_reason", "stop"),
            created_at=str(int(time.time()))
        )
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        pricing = {
            "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
            "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125}
        }
        
        if model not in pricing:
            return 0.0
            
        return (
            (prompt_tokens / 1000) * pricing[model]["prompt"] +
            (completion_tokens / 1000) * pricing[model]["completion"]
        )

class ProviderFactory:
    @staticmethod
    def get_provider(provider: Provider) -> LLMProvider:
        if provider == Provider.OPENAI:
            return OpenAIProvider()
        elif provider == Provider.ANTHROPIC:
            return AnthropicProvider()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    def get_default_provider(model: str) -> Provider:
        if model in settings.openai_models:
            return Provider.OPENAI
        elif model in settings.anthropic_models:
            return Provider.ANTHROPIC
        else:
            return Provider.OPENAI  # fallback

