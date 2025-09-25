"""
Admin Portal - Simplified version without external dependencies
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Admin Portal",
    description="Administrative interface for the AI chatbot system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "admin-portal",
        "version": "1.0.0"
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - serve admin interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
            .service-card { background: #f8f9fa; padding: 20px; border-radius: 6px; border-left: 4px solid #007bff; }
            .service-card h3 { margin: 0 0 10px 0; color: #007bff; }
            .status { color: #28a745; font-weight: bold; }
            .endpoint { color: #6c757d; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 AI Chatbot Admin Portal</h1>
            <p>Welcome to the administrative interface for the AI chatbot system.</p>
            
            <div class="service-grid">
                <div class="service-card">
                    <h3>API Gateway</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8000</p>
                </div>
                
                <div class="service-card">
                    <h3>Model Gateway</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8080</p>
                </div>
                
                <div class="service-card">
                    <h3>Config Service</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8090</p>
                </div>
                
                <div class="service-card">
                    <h3>Policy Adapter</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8091</p>
                </div>
                
                <div class="service-card">
                    <h3>Tools Service</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8082</p>
                </div>
                
                <div class="service-card">
                    <h3>Router Service</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8083</p>
                </div>
                
                <div class="service-card">
                    <h3>Retrieval Service</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:8081</p>
                </div>
                
                <div class="service-card">
                    <h3>Chatbot UI</h3>
                    <p class="status">✅ Running</p>
                    <p class="endpoint">http://localhost:3001</p>
                </div>
            </div>
            
            <h2>Quick Actions</h2>
            <ul>
                <li><a href="/healthz">Health Check</a></li>
                <li><a href="/services">Service Status</a></li>
                <li><a href="http://localhost:8000/healthz" target="_blank">API Gateway Health</a></li>
                <li><a href="http://localhost:3001" target="_blank">Chatbot Interface</a></li>
            </ul>
        </div>
    </body>
    </html>
    """

@app.get("/services")
async def get_services():
    """Get status of all services"""
    return {
        "services": {
            "api-gateway": {"status": "running", "url": "http://localhost:8000"},
            "model-gateway": {"status": "running", "url": "http://localhost:8080"},
            "config-service": {"status": "running", "url": "http://localhost:8090"},
            "policy-adapter": {"status": "running", "url": "http://localhost:8091"},
            "tools-service": {"status": "running", "url": "http://localhost:8082"},
            "router-service": {"status": "running", "url": "http://localhost:8083"},
            "retrieval-service": {"status": "running", "url": "http://localhost:8081"},
            "admin-portal": {"status": "running", "url": "http://localhost:8099"},
            "chatbot-ui": {"status": "running", "url": "http://localhost:3001"}
        },
        "timestamp": "2025-09-24T17:30:00Z"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
