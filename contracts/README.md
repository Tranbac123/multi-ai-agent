# Shared Platform Contracts

This directory contains truly shared schemas and types used across multiple services in the Multi-AI-Agent platform.

## ⚠️ **Important Guidelines**

### What Belongs Here
- **Shared enums** used by 3+ services (e.g., PlanTier, Status codes)
- **Common data structures** (e.g., TenantContext, PaginationRequest)
- **Standard error formats** (e.g., ErrorResponse)
- **Cross-cutting types** (e.g., AuditMetadata)

### What Does NOT Belong Here
- **Service-specific schemas** (belong in `apps/<service>/contracts/`)
- **Internal service models** (not exposed via API)
- **Temporary or experimental types**
- **Single-service enums or types**

## 📁 Files

### `shared.yaml`
OpenAPI 3.0 shared schemas for HTTP services.

### `shared.proto`
Protocol Buffer shared definitions for gRPC services.

## 🔄 Versioning Strategy

### Semantic Versioning
- **Major version** (v2.0.0): Breaking changes requiring all services to update
- **Minor version** (v1.1.0): New optional fields or types
- **Patch version** (v1.0.1): Bug fixes and clarifications

### Breaking Change Process
1. **Deprecation**: Mark old fields as deprecated in v1.x
2. **Transition Period**: Services update to use new fields
3. **Removal**: Remove deprecated fields in v2.0
4. **Communication**: Announce breaking changes 30 days in advance

### Backwards Compatibility
- ✅ **Adding optional fields**: Safe, increment minor version
- ✅ **Adding new enum values**: Safe with proper handling
- ✅ **Deprecating fields**: Safe, mark with `deprecated: true`
- ❌ **Removing fields**: Breaking change, requires major version
- ❌ **Changing field types**: Breaking change
- ❌ **Making optional fields required**: Breaking change

## 🔧 Code Generation

### Generate Clients
```bash
# Generate all language clients
make generate-shared-clients

# Language-specific generation
make generate-go-shared
make generate-python-shared  
make generate-typescript-shared
```

### Using Shared Types

#### In Service OpenAPI Specs
```yaml
# Reference shared schemas
components:
  schemas:
    UserResponse:
      allOf:
        - $ref: '../../../contracts/shared.yaml#/components/schemas/AuditMetadata'
        - type: object
          properties:
            name:
              type: string
```

#### In Service Proto Files
```protobuf
import "contracts/shared.proto";

message User {
  string name = 1;
  platform.shared.v1.AuditMetadata audit = 2;
}
```

## 📊 Usage Tracking

### Current Consumers

| Schema | Services Using | Version |
|--------|---------------|---------|
| `TenantContext` | api-gateway, billing-service, tenant-service | v1.0.0 |
| `ErrorResponse` | All HTTP services | v1.0.0 |
| `PaginationRequest` | analytics-service, admin-portal | v1.0.0 |
| `AuditMetadata` | tenant-service, billing-service | v1.0.0 |

### Change Impact Analysis

Before making changes:
1. Check usage in all services
2. Assess backward compatibility impact
3. Plan migration strategy for breaking changes
4. Update all consuming services simultaneously

## 🚀 Best Practices

### Schema Design
- **Use descriptive names**: `PlanTier` not `Tier`
- **Include descriptions**: Every field should have clear documentation
- **Follow conventions**: Use `snake_case` for fields, `PascalCase` for types
- **Validate constraints**: Use appropriate formats, minimums, maximums

### Evolution Strategy
- **Start restrictive**: Easier to loosen constraints than tighten them
- **Plan for growth**: Consider future use cases in initial design
- **Document decisions**: Include reasoning in schema descriptions
- **Test thoroughly**: Validate with all consuming services

## 📞 Contact

For questions about shared contracts:
- **Platform Team**: platform@company.com
- **Architecture Reviews**: Schedule via #architecture channel
- **Breaking Changes**: Notify #breaking-changes channel