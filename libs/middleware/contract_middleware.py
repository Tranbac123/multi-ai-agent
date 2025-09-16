"""
Contract Middleware for API Gateway

Enforces strict contract validation at API boundaries.
"""

from typing import Dict, Any, Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import json

from libs.contracts.validation import (
    validate_contract, ContractValidationError, 
    create_error_response, sanitize_for_logging
)

logger = structlog.get_logger(__name__)


class ContractMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing contract validation at API boundaries."""
    
    def __init__(
        self, 
        app,
        request_contracts: Optional[Dict[str, Any]] = None,
        response_contracts: Optional[Dict[str, Any]] = None,
        enable_pii_redaction: bool = True
    ):
        super().__init__(app)
        self.request_contracts = request_contracts or {}
        self.response_contracts = response_contracts or {}
        self.enable_pii_redaction = enable_pii_redaction
        
        logger.info("Contract middleware initialized", 
                   request_endpoints=len(self.request_contracts),
                   response_endpoints=len(self.response_contracts))
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through contract validation."""
        
        # Skip validation for certain paths
        if self._should_skip_validation(request):
            return await call_next(request)
        
        # Validate request
        validated_request = await self._validate_request(request)
        
        # Process request
        response = await call_next(validated_request)
        
        # Validate response
        validated_response = await self._validate_response(response, request)
        
        return validated_response
    
    def _should_skip_validation(self, request: Request) -> bool:
        """Check if validation should be skipped for this request."""
        skip_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    async def _validate_request(self, request: Request) -> Request:
        """Validate request against contract."""
        endpoint_key = f"{request.method}:{request.url.path}"
        
        if endpoint_key not in self.request_contracts:
            # No contract defined for this endpoint
            return request
        
        contract_class = self.request_contracts[endpoint_key]
        
        try:
            # Read request body
            body = await request.body()
            
            if not body:
                # Empty body - validate empty request
                validated_data = validate_contract({}, contract_class, strict=True, forbid_extra=True)
            else:
                # Parse and validate JSON body
                try:
                    request_data = json.loads(body.decode('utf-8'))
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON in request", 
                               endpoint=endpoint_key, 
                               error=str(e))
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid JSON: {e}"
                    )
                
                # Sanitize for logging if PII redaction is enabled
                if self.enable_pii_redaction:
                    sanitized_data = sanitize_for_logging(request_data)
                    logger.info("Validating request", 
                              endpoint=endpoint_key,
                              contract_class=contract_class.__name__,
                              data_keys=list(sanitized_data.keys()) if isinstance(sanitized_data, dict) else None)
                else:
                    logger.info("Validating request", 
                              endpoint=endpoint_key,
                              contract_class=contract_class.__name__)
                
                # Validate against contract
                validated_data = validate_contract(request_data, contract_class, strict=True, forbid_extra=True)
            
            # Store validated data in request state
            request.state.validated_data = validated_data
            
            logger.info("Request validation successful", 
                       endpoint=endpoint_key,
                       contract_class=contract_class.__name__)
            
            return request
            
        except ContractValidationError as e:
            logger.error("Request validation failed", 
                        endpoint=endpoint_key,
                        contract_class=contract_class.__name__,
                        errors=e.errors)
            
            error_response = create_error_response(e, status.HTTP_422_UNPROCESSABLE_ENTITY)
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response
            )
        
        except Exception as e:
            logger.error("Unexpected validation error", 
                        endpoint=endpoint_key,
                        error=str(e))
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "type": "internal_error",
                        "message": "Internal validation error",
                        "status_code": 500
                    }
                }
            )
    
    async def _validate_response(self, response: Response, request: Request) -> Response:
        """Validate response against contract."""
        endpoint_key = f"{request.method}:{request.url.path}"
        
        if endpoint_key not in self.response_contracts:
            # No contract defined for this endpoint
            return response
        
        # Only validate successful responses
        if response.status_code >= 400:
            return response
        
        contract_class = self.response_contracts[endpoint_key]
        
        try:
            # Read response body
            body = response.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            
            if not body:
                # Empty response body
                return response
            
            # Parse JSON response
            try:
                response_data = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in response", 
                           endpoint=endpoint_key, 
                           error=str(e))
                # Don't fail the response, just log the error
                return response
            
            # Validate against contract
            validated_data = validate_contract(response_data, contract_class, strict=True, forbid_extra=True)
            
            logger.info("Response validation successful", 
                       endpoint=endpoint_key,
                       contract_class=contract_class.__name__)
            
            return response
            
        except ContractValidationError as e:
            logger.error("Response validation failed", 
                        endpoint=endpoint_key,
                        contract_class=contract_class.__name__,
                        errors=e.errors)
            
            # Don't fail the response, just log the error
            # In production, you might want to fail fast on response validation errors
            return response
        
        except Exception as e:
            logger.error("Unexpected response validation error", 
                        endpoint=endpoint_key,
                        error=str(e))
            
            return response


class ContractValidator:
    """Utility class for contract validation."""
    
    @staticmethod
    def validate_inter_service_payload(
        payload: Dict[str, Any],
        contract_class: Any,
        service_name: str,
        operation: str
    ) -> Any:
        """Validate inter-service communication payload."""
        try:
            logger.debug("Validating inter-service payload", 
                        service=service_name,
                        operation=operation,
                        contract_class=contract_class.__name__)
            
            validated_payload = validate_contract(payload, contract_class, strict=True, forbid_extra=True)
            
            logger.debug("Inter-service payload validation successful", 
                        service=service_name,
                        operation=operation,
                        contract_class=contract_class.__name__)
            
            return validated_payload
            
        except ContractValidationError as e:
            logger.error("Inter-service payload validation failed", 
                        service=service_name,
                        operation=operation,
                        contract_class=contract_class.__name__,
                        errors=e.errors)
            raise
        
        except Exception as e:
            logger.error("Unexpected inter-service validation error", 
                        service=service_name,
                        operation=operation,
                        contract_class=contract_class.__name__,
                        error=str(e))
            raise ContractValidationError(f"Inter-service validation error: {e}")
    
    @staticmethod
    def validate_agent_request(
        request_data: Dict[str, Any],
        agent_id: str
    ) -> Any:
        """Validate agent request with specific agent contract."""
        from libs.contracts.agent_spec import AgentSpec
        
        return ContractValidator.validate_inter_service_payload(
            payload=request_data,
            contract_class=AgentSpec,
            service_name="agent_service",
            operation=f"agent_request_{agent_id}"
        )
    
    @staticmethod
    def validate_tool_request(
        request_data: Dict[str, Any],
        tool_id: str
    ) -> Any:
        """Validate tool request with specific tool contract."""
        from libs.contracts.tool_spec import ToolInput
        
        return ContractValidator.validate_inter_service_payload(
            payload=request_data,
            contract_class=ToolInput,
            service_name="tool_service",
            operation=f"tool_request_{tool_id}"
        )
    
    @staticmethod
    def validate_router_request(
        request_data: Dict[str, Any]
    ) -> Any:
        """Validate router request with router contract."""
        from libs.contracts.router_spec import RouterDecisionRequest
        
        return ContractValidator.validate_inter_service_payload(
            payload=request_data,
            contract_class=RouterDecisionRequest,
            service_name="router_service",
            operation="router_decision"
        )
    
    @staticmethod
    def validate_message(
        message_data: Dict[str, Any]
    ) -> Any:
        """Validate message with message contract."""
        from libs.contracts.message_spec import MessageSpec
        
        return ContractValidator.validate_inter_service_payload(
            payload=message_data,
            contract_class=MessageSpec,
            service_name="message_service",
            operation="process_message"
        )


def create_contract_middleware(
    app,
    request_contracts: Optional[Dict[str, Any]] = None,
    response_contracts: Optional[Dict[str, Any]] = None,
    enable_pii_redaction: bool = True
) -> ContractMiddleware:
    """Create and configure contract middleware."""
    
    # Default request contracts for common endpoints
    default_request_contracts = {
        "POST:/api/v1/agents": "AgentSpec",
        "POST:/api/v1/messages": "MessageSpec",
        "POST:/api/v1/tools": "ToolInput",
        "POST:/api/v1/router/decide": "RouterDecisionRequest",
    }
    
    # Default response contracts for common endpoints
    default_response_contracts = {
        "POST:/api/v1/router/decide": "RouterDecisionResponse",
        "POST:/api/v1/tools": "ToolOutput",
        "GET:/api/v1/agents": "List[AgentSpec]",
    }
    
    # Merge with provided contracts
    if request_contracts:
        default_request_contracts.update(request_contracts)
    
    if response_contracts:
        default_response_contracts.update(response_contracts)
    
    return ContractMiddleware(
        app=app,
        request_contracts=default_request_contracts,
        response_contracts=default_response_contracts,
        enable_pii_redaction=enable_pii_redaction
    )
