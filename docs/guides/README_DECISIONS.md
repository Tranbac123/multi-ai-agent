# DECISION PACK – IMPLEMENT

Dry-run:

```bash
python scripts/decisions_apply.py
```

Apply changes:

```bash
python scripts/decisions_apply.py --apply
```

## What This Script Does

1. **Adds model-gateway** (port 8083) with provider routing, authz, and metering
2. **Renames chat-adapters** → chat-adapters-service (port 8082)
3. **Moves eval/** → docs/evaluation/ (avoid naming conflict)
4. **Adds semantic-cache-service** (port 8088) for LLM response caching
5. **Adds notification-service** (port 8097) for email/Slack/webhooks
6. **Cleans contracts/** - moves service-specific files to service directories
7. **Updates CI workflows** - adds path filters for new services
8. **Scaffolds observability** - copies templates to each service

## Service Architecture

### Data-Plane Services

- **model-gateway**: LLM provider abstraction with circuit breaker
- **chat-adapters-service**: Multi-platform chat integrations
- **semantic-cache-service**: Semantic similarity caching

### Control-Plane Services

- **notification-service**: Multi-channel notification delivery

## Files Created/Modified

### New Services

- `apps/data-plane/model-gateway/` - Complete service with provider routing
- `apps/data-plane/semantic-cache-service/` - Simple cache implementation
- `apps/control-plane/notification-service/` - Notification delivery

### Enhanced Services

- `apps/data-plane/chat-adapters-service/` - Renamed and scaffolded

### Documentation

- `docs/evaluation/` - Moved from `eval/` to avoid conflicts

### Contracts Cleanup

- Service-specific contracts moved to `apps/<service>/contracts/`
- Root `contracts/` keeps only shared schemas

## Validation

After running `--apply`:

1. Review `git diff` to see all changes
2. Test each service: `make run` in service directory
3. Verify CI paths in `.github/workflows/`
4. Check observability scaffolding in each service
