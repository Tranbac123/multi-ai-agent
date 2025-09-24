import asyncio
import time
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json

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

@app.get("/healthz")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

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
        if OPENAI_API_KEY:
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
    """Handle request using direct OpenAI API"""
    citations = []
    trace = ["Using direct OpenAI API"]
    
    try:
        async with httpx.AsyncClient() as client:
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
                        {"role": "system", "content": "You are a helpful AI assistant. Provide clear, accurate, and helpful responses."},
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
                
                # Add a citation if this is about general knowledge
                if "what" in query.lower() or "how" in query.lower() or "why" in query.lower():
                    citations.append("[1] Information provided by OpenAI GPT-4")
                
                return answer, citations, trace
            else:
                raise Exception(f"OpenAI API error: {response.status_code}")
                
    except Exception as e:
        trace.append(f"OpenAI API error: {str(e)}")
        # Fallback to simple response
        return "I apologize, but I'm having trouble connecting to the AI service right now. Please try again later.", citations, trace

async def handle_model_gateway_request(query: str):
    """Handle request using model gateway service"""
    citations = []
    trace = ["Using model gateway service"]
    
    try:
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
        # Fallback to simple response
        return "I apologize, but I'm having trouble connecting to the AI service right now. Please try again later.", citations, trace

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Standard chat endpoint for other services.
    """
    try:
        if OPENAI_API_KEY:
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
            raise HTTPException(status_code=503, detail="No OpenAI API key configured")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

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
