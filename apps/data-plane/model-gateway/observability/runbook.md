# Model Gateway Runbook

## Service Overview

Model Gateway provides unified access to multiple LLM providers (OpenAI, Anthropic, Azure) with circuit breaker, rate limiting, and token metering capabilities.

## Common Issues

### High Error Rate

1. **Check provider status**: `kubectl logs -l app=model-gateway | grep "Provider error"`
2. **Check circuit breaker states**: GET `/v1/health` endpoint
3. **Verify API keys**: Check secret `model-gateway-secrets`
4. **Check rate limits**: Monitor rate limiting logs

### High Latency

1. **Check provider response times**: Monitor provider-specific metrics
2. **Check circuit breaker timeouts**: Review circuit breaker configuration
3. **Scale service**: Increase replicas if CPU/memory high
4. **Check network**: Verify connectivity to provider APIs

### Circuit Breaker Open

1. **Identify affected provider**: Check `/v1/providers/{provider}/status`
2. **Check provider health**: Test direct API calls to provider
3. **Reset circuit breaker**: Restart service if needed
4. **Switch to backup provider**: Update routing configuration

### Rate Limit Exceeded

1. **Check tenant usage**: Review rate limiting metrics by tenant
2. **Increase limits**: Update rate limiting configuration
3. **Scale service**: Add more replicas to handle load
4. **Implement queuing**: Consider adding request queuing

## Key Commands

```bash
# Check service health
kubectl get pods -l app=model-gateway
curl http://model-gateway/healthz
curl http://model-gateway/v1/health

# Check logs
kubectl logs -l app=model-gateway --tail=100

# Check provider status
curl http://model-gateway/v1/providers/openai/status

# Scale service
kubectl scale deployment model-gateway --replicas=5

# Check secrets
kubectl get secret model-gateway-secrets -o yaml

# Check circuit breaker metrics
curl http://model-gateway/v1/health | jq .circuit_breakers
```

## Escalation

- **Primary**: Platform Engineering Team
- **Secondary**: AI/ML Engineering Team
- **PagerDuty**: #model-gateway-critical

## Related Services

- `policy-adapter`: Tenant authorization
- `usage-metering`: Token billing
- `api-gateway`: Upstream routing

