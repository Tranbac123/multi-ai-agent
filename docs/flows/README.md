# Service Flow Diagrams

This directory contains detailed flow diagrams showing how requests travel across services in the Multi-AI-Agent Platform during local development. These diagrams illustrate the step-by-step interactions between services, including ports, protocols, headers, payload summaries, side-effects, and outputs.

## 📊 System Overview

The platform consists of **20+ services** organized into three main layers:

- **Frontend Layer**: 3 services (Web Frontend, AI Chatbot UI, Admin Portal)
- **Data Plane**: 10 services (API Gateway, Model Gateway, Retrieval, Tools, Router, etc.)
- **Control Plane**: 7 services (Config, Policy, Feature Flags, Usage Metering, etc.)
- **Infrastructure**: 4 services (PostgreSQL, Redis, NATS, Vector DB)

## 🎨 **NEW: Detailed Visual Flows**

For a comprehensive visual understanding of the system, check out these enhanced diagrams:

### **🌟 Recommended Visual Flows**
1. **[detailed-visual-flow.mmd](detailed-visual-flow.mmd)** - Enhanced system map with emojis and detailed service descriptions
2. **[detailed-sequence-flow.mmd](detailed-sequence-flow.mmd)** - Step-by-step user journey with visual elements and detailed interactions
3. **[comprehensive-data-flow.mmd](comprehensive-data-flow.mmd)** - Complete data flow showing all input types and processing paths
4. **[complete-architecture-flow.mmd](complete-architecture-flow.mmd)** - Full architecture with all layers, services, and connections

These diagrams provide:
- 🎨 **Visual Enhancement**: Emojis and color coding for better readability
- 📊 **Detailed Descriptions**: Comprehensive service features and capabilities
- 🔄 **Complete Flows**: End-to-end request processing with all interactions
- 🎯 **Multiple Perspectives**: System map, sequence, data flow, and architecture views

## 🗺️ Diagrams Overview

| Diagram | Format | Description | Key Flows |
|---------|--------|-------------|-----------|
| [system-map.mmd](system-map.mmd) | Mermaid | Complete system architecture with all services and connections | All services, external APIs, infrastructure |
| [detailed-visual-flow.mmd](detailed-visual-flow.mmd) | Mermaid | **Enhanced visual system map with detailed service descriptions** | **Complete architecture with emojis and detailed features** |
| [detailed-sequence-flow.mmd](detailed-sequence-flow.mmd) | Mermaid | **Detailed step-by-step sequence with visual elements** | **Complete user journey with emojis and detailed interactions** |
| [comprehensive-data-flow.mmd](comprehensive-data-flow.mmd) | Mermaid | **Comprehensive data flow showing all input types and processing paths** | **Chat, Documents, Social, Admin processing paths** |
| [complete-architecture-flow.mmd](complete-architecture-flow.mmd) | Mermaid | **Complete architecture with all layers and detailed connections** | **Full system with all services, features, and connections** |
| [flow-web-chat.mmd](flow-web-chat.mmd) | Mermaid | End-to-end web chat flow with real-time search | User → Chatbot → API Gateway → AI + Web Search |
| [flow-chat-adapters.mmd](flow-chat-adapters.mmd) | Mermaid | Multi-channel chat integration (Facebook, Zalo, TikTok) | Social platforms → Chat Adapters → Core services |
| [flow-ingestion.mmd](flow-ingestion.mmd) | Mermaid | Document upload, processing, and semantic search | Document upload → Vector indexing → Search |
| [flow-retrieval.mmd](flow-retrieval.mmd) | Mermaid | Complex retrieval with router intelligence | Query → Router → Retrieval → AI processing |
| [flow-billing-analytics.mmd](flow-billing-analytics.mmd) | Mermaid | Usage tracking, billing, and analytics | Usage events → Billing → Invoice generation |

### PlantUML Variants

| Diagram | Format | Description |
|---------|--------|-------------|
| [c4-context.puml](c4-context.puml) | PlantUML | C4 Context diagram showing system boundaries |
| [flow-web-chat.puml](flow-web-chat.puml) | PlantUML | PlantUML version of web chat flow |
| [flow-chat-adapters.puml](flow-chat-adapters.puml) | PlantUML | PlantUML version of chat adapters flow |
| [flow-ingestion.puml](flow-ingestion.puml) | PlantUML | PlantUML version of ingestion flow |
| [flow-retrieval.puml](flow-retrieval.puml) | PlantUML | PlantUML version of retrieval flow |
| [flow-billing-analytics.puml](flow-billing-analytics.puml) | PlantUML | PlantUML version of billing flow |

## 🛠️ How to Render

### Mermaid CLI

```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Render system map
mmdc -i docs/flows/system-map.mmd -o docs/flows/system-map.png

# Render all flow diagrams
mmdc -i docs/flows/flow-web-chat.mmd -o docs/flows/flow-web-chat.png
mmdc -i docs/flows/flow-chat-adapters.mmd -o docs/flows/flow-chat-adapters.png
mmdc -i docs/flows/flow-ingestion.mmd -o docs/flows/flow-ingestion.png
mmdc -i docs/flows/flow-retrieval.mmd -o docs/flows/flow-retrieval.png
mmdc -i docs/flows/flow-billing-analytics.mmd -o docs/flows/flow-billing-analytics.png
```

### PlantUML

```bash
# Install PlantUML
brew install plantuml  # macOS
# or download from https://plantuml.com/download

# Render C4 context diagram
plantuml -tpng docs/flows/c4-context.puml

# Render all PlantUML flow diagrams
plantuml -tpng docs/flows/flow-*.puml
```

### Online Rendering

- **Mermaid**: Use [Mermaid Live Editor](https://mermaid.live/)
- **PlantUML**: Use [PlantUML Online Server](http://www.plantuml.com/plantuml/uml/)

## 🔍 Key Service Ports

### Frontend Services
- **AI Chatbot UI**: `:3001` (React)
- **Web Frontend**: `:3000` (React/Vite)
- **Admin Portal**: `:8099` (FastAPI)

### Data Plane Services
- **API Gateway**: `:8000` (FastAPI)
- **Model Gateway**: `:8080` (AI Routing)
- **Retrieval Service**: `:8081` (RAG)
- **Tools Service**: `:8082` (FIRECRAWL)
- **Router Service**: `:8083` (Routing)
- **Realtime Gateway**: `:8084` (WebSocket)
- **Chat Adapters**: `:8006` (Multi-channel)

### Control Plane Services
- **Config Service**: `:8090` (Configuration)
- **Policy Adapter**: `:8091` (Policies)
- **Feature Flags**: `:8092` (Toggles)
- **Registry Service**: `:8094` (Discovery)
- **Usage Metering**: `:8095` (Billing)
- **Audit Log**: `:8096` (Compliance)
- **Notifications**: `:8097` (Alerts)

### Infrastructure
- **PostgreSQL**: `:5432` (Database)
- **Redis**: `:6379` (Cache/Sessions)
- **NATS JetStream**: `:4222` (Events)

## 🔄 Protocol Patterns

### HTTP/REST
- **Solid edges** in Mermaid diagrams
- Standard REST API calls with JSON payloads
- Headers: `Authorization`, `X-Request-Id`, `X-Tenant-Id`

### WebSocket
- **Thick edges** in Mermaid diagrams
- Real-time bidirectional communication
- Used for streaming responses and live updates

### Event Streaming
- **Dashed edges** in Mermaid diagrams
- NATS JetStream for reliable event delivery
- Topics: `tenant.usage.*`, `tenant.audit.*`, `tenant.alerts.*`

### gRPC
- **Dotted edges** in Mermaid diagrams
- High-performance inter-service communication
- Protocol buffers for serialization

## 🚨 Error Handling

Each flow diagram includes error handling branches showing:

- **Service Unavailability**: Graceful degradation and fallbacks
- **API Rate Limits**: Retry logic with exponential backoff
- **Timeout Scenarios**: Circuit breaker patterns
- **Data Validation**: Input validation and error responses

## 📈 Performance Considerations

### Caching Strategy
- **Redis**: Session storage, feature flags, usage counters
- **Application Cache**: Query results, embeddings, analytics
- **CDN**: Static assets and API responses

### Load Balancing
- **API Gateway**: Request distribution and health checks
- **Router Service**: Intelligent tier selection
- **Model Gateway**: Provider failover and load balancing

### Monitoring
- **Usage Tracking**: Real-time cost monitoring and alerts
- **Audit Logging**: Comprehensive activity tracking
- **Performance Metrics**: Response times, throughput, error rates

## 🔐 Security Features

### Authentication & Authorization
- **JWT Tokens**: Stateless authentication
- **Tenant Isolation**: Row-level security (RLS)
- **API Key Management**: Secure external API access

### Data Protection
- **PII Detection**: Automatic sensitive data identification
- **Field-level Encryption**: KMS integration for sensitive fields
- **Audit Trail**: Complete activity logging for compliance

## 📚 Additional Resources

- **[Services Catalog](../SERVICES_CATALOG.md)** - Complete service directory
- **[System Overview](../SYSTEM_OVERVIEW.md)** - Detailed architecture documentation
- **[API Contracts](../CONTRACTS.md)** - Request/response schemas
- **[Testing Overview](../testing/TESTING_OVERVIEW.md)** - Testing framework documentation

---

_Generated from codebase analysis on $(date)_  
_Total Services Mapped: 20+ (13 Core + 7 Infrastructure)_  
_Endpoints Documented: 50+ across all services_
