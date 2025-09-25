import asyncio
import time
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json
import psycopg2
import redis

app = FastAPI(title="API Gateway", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_GATEWAY_URL = os.getenv("MODEL_GATEWAY_URL", "http://model-gateway:8080")
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval-service:8081")
TOOLS_SERVICE_URL = os.getenv("TOOLS_SERVICE_URL", "http://tools-service:8082")

# Request/Response models
class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class AskResponse(BaseModel):
    answer: str
    citations: List[str] = []
    trace: List[str] = []

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "gpt-4o-mini"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000

class ChatResponse(BaseModel):
    content: str
    usage: Optional[Dict[str, Any]] = None

class WebScrapeRequest(BaseModel):
    url: str

class WebScrapeResponse(BaseModel):
    success: bool
    content: str
    execution_time_ms: int

@app.get("/healthz")
def health_check():
    """Health check endpoint with database connectivity tests"""
    health_status = {
        "status": "healthy", 
        "timestamp": time.time(),
        "services": {}
    }
    
    # Test PostgreSQL connection
    try:
        conn = psycopg2.connect(
            host="postgres",
            port=5432,
            user="postgres",
            password="postgres",
            dbname="ai_agent"
        )
        conn.close()
        health_status["services"]["postgresql"] = "connected"
    except Exception as e:
        health_status["services"]["postgresql"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Test Redis connection
    try:
        r = redis.Redis(host="redis", port=6379, decode_responses=True)
        r.ping()
        health_status["services"]["redis"] = "connected"
    except Exception as e:
        health_status["services"]["redis"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "API Gateway",
        "version": "0.1.0",
        "endpoints": {
            "health": "/healthz",
            "ask": "/ask",
            "chat": "/v1/chat",
            "web_scrape": "/web-scrape"
        }
    }

@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Main endpoint for the chatbot frontend.
    Handles questions and returns answers with citations and trace information.
    """
    try:
        # Step 1: Log the incoming request
        trace = [f"Received question: {request.query[:100]}..."]
        
        # Step 2: Check if we have OpenAI API key for direct calls
        if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("your_"):
            # Direct OpenAI integration
            answer, citations, additional_trace = await handle_openai_request(request.query)
        else:
            # Use model gateway
            answer, citations, additional_trace = await handle_model_gateway_request(request.query)
        
        trace.extend(additional_trace)
        
        return AskResponse(
            answer=answer,
            citations=citations,
            trace=trace
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")

async def handle_openai_request(query: str):
    """Handle request using direct OpenAI API with web scraping capabilities"""
    citations = []
    trace = ["Using direct OpenAI API"]
    
    # Check if the query is asking for web search or live data
    web_keywords = ["latest", "current", "news", "hacker news", "real-time", "today", "recent", "live", "search", "browse", "internet", "website", "site"]
    needs_web_data = any(keyword in query.lower() for keyword in web_keywords)
    
    web_content = ""
    if needs_web_data:
        trace.append("Detected web search request, attempting to fetch live data")
        web_content = await try_web_scraping(query)
        if web_content:
            trace.append("Successfully fetched web content")
            citations.append("[1] Live web data via FIRECRAWL")
        else:
            trace.append("Web scraping failed, proceeding with AI response only")
    
    try:
        async with httpx.AsyncClient() as client:
            # Prepare the system message with web content if available
            system_message = "You are a helpful AI assistant with access to live web data. You can search the internet and provide real-time information. Provide clear, accurate, and helpful responses based on the current data available to you."
            if web_content:
                system_message += f"\n\nYou have successfully accessed live web data: {web_content[:1000]}... Use this information to provide current, real-time responses about what you found on the web."
            
            # Call OpenAI API directly
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                trace.append("OpenAI API call successful")
                
                # Add citations
                if web_content:
                    citations.append("[1] Live web data via FIRECRAWL")
                if "what" in query.lower() or "how" in query.lower() or "why" in query.lower():
                    citations.append("[2] Information provided by OpenAI GPT-4")
                
                return answer, citations, trace
            else:
                raise Exception(f"OpenAI API error: {response.status_code}")
                
    except Exception as e:
        trace.append(f"OpenAI API error: {str(e)}")
        # Fallback to simple response
        return "I apologize, but I'm having trouble connecting to the AI service right now. Please try again later.", citations, trace

async def try_web_scraping(query: str):
    """Attempt to search web content using FIRECRAWL search API"""
    try:
        # Extract potential URLs from the query first
        import re
        urls = re.findall(r'https?://[^\s]+', query)
        
        if urls:
            # If there are specific URLs, scrape them
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TOOLS_SERVICE_URL}/v1/tools/exec",
                    json={
                        "name": "web_scrape",
                        "args": {"url": urls[0]}
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("output", "")
        else:
            # Use FIRECRAWL search for general queries
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TOOLS_SERVICE_URL}/v1/tools/exec",
                    json={
                        "name": "web_search",
                        "args": {"query": query}
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("output", "")
        
        return ""
    except Exception as e:
        print(f"Web scraping error: {e}")
        return ""

async def handle_model_gateway_request(query: str):
    """Handle request using model gateway service or provide helpful fallback"""
    citations = []
    trace = ["No valid OpenAI API key found, using fallback response"]
    
    try:
        # Try model gateway first
        async with httpx.AsyncClient() as client:
            # Call model gateway
            response = await client.post(
                f"{MODEL_GATEWAY_URL}/v1/chat",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant."},
                        {"role": "user", "content": query}
                    ],
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("content", "No response received")
                trace.append("Model gateway call successful")
                citations.append("[1] Information provided by AI Assistant")
                return answer, citations, trace
            else:
                raise Exception(f"Model gateway error: {response.status_code}")
                
    except Exception as e:
        trace.append(f"Model gateway error: {str(e)}")
        # Provide a helpful fallback response instead of error
        fallback_answer = f"I received your question: '{query}'. However, I need a valid OpenAI API key to provide AI responses. Please configure your OPENAI_API_KEY environment variable with a real API key from https://platform.openai.com/api-keys"
        return fallback_answer, citations, trace

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Standard chat endpoint for other services.
    """
    try:
        if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("your_"):
            # Direct OpenAI integration
            async with httpx.AsyncClient() as client:
                messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
                
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": request.model,
                        "messages": messages,
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return ChatResponse(
                        content=data["choices"][0]["message"]["content"],
                        usage=data.get("usage")
                    )
                else:
                    raise HTTPException(status_code=response.status_code, detail="OpenAI API error")
        else:
            return ChatResponse(
                content="Chat functionality requires a valid OpenAI API key. Please configure OPENAI_API_KEY in your environment.",
                usage=None
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/web-scrape", response_model=WebScrapeResponse)
async def web_scrape(request: WebScrapeRequest):
    """
    Web scraping endpoint using FIRECRAWL via tools-service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TOOLS_SERVICE_URL}/v1/tools/exec",
                json={
                    "name": "web_scrape",
                    "args": {"url": request.url}
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return WebScrapeResponse(
                    success=data["success"],
                    content=data["output"],
                    execution_time_ms=data["execution_time_ms"]
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Tools service error")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Web scraping error: {str(e)}")

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "API Gateway",
        "version": "0.1.0",
        "endpoints": {
            "health": "/healthz",
            "chat": "/v1/chat",
            "ask": "/ask"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
