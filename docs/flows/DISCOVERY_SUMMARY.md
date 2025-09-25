
## 🔍 Service Discovery Summary

### Services Discovered: 20+ Services
- **Frontend Services**: 3 (AI Chatbot UI, Web Frontend, Admin Portal)
- **Data Plane Services**: 10 (API Gateway, Model Gateway, Retrieval, Tools, Router, etc.)
- **Control Plane Services**: 7 (Config, Policy, Feature Flags, Usage Metering, etc.)
- **Infrastructure Services**: 4 (PostgreSQL, Redis, NATS, Vector DB)

### Ports Mapped: 15+ Unique Ports
- Frontend: 3000, 3001, 8099
- Data Plane: 8000, 8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8006
- Control Plane: 8090, 8091, 8092, 8094, 8095, 8096, 8097
- Infrastructure: 5432, 6379, 4222, 8222

### Endpoints Documented: 50+ Endpoints
- API Gateway: /healthz, /ask, /v1/chat, /web-scrape
- Tools Service: /v1/tools, /v1/tools/exec
- Retrieval Service: /search
- Router Service: /route
- Chat Adapters: /facebook/webhook, /zalo/webhook, /tiktok/webhook
- Control Plane: Various config, usage, and admin endpoints

### Protocols Used:
- HTTP/REST: Primary communication protocol
- WebSocket: Real-time communication (Realtime Gateway)
- NATS JetStream: Event streaming and message queuing
- External APIs: OpenAI, Anthropic, FIRECRAWL, Stripe

### Key Features Implemented:
- Real-time web search with FIRECRAWL integration
- Multi-channel chat adapters (Facebook, Zalo, TikTok)
- Intelligent request routing with tier selection
- Document ingestion and semantic search
- Usage tracking and billing automation
- Comprehensive audit logging and compliance

### Files Generated: 15 Files
- 6 Mermaid diagrams (.mmd)
- 6 PlantUML diagrams (.puml)
- 1 comprehensive README.md
- 1 Postman collection (.json)
- 1 k6 smoke test script (.js)

### Error Handling Coverage:
- Service unavailability fallbacks
- API rate limit handling
- Timeout scenarios with circuit breakers
- Data validation and error responses
- Graceful degradation patterns

### Performance Considerations:
- Redis caching for sessions and features
- Vector database for embeddings
- Load balancing and health checks
- Real-time monitoring and alerting
- Cost optimization and usage tracking

All diagrams include proper error branches, side-effects, and background processing patterns.

