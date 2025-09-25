from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import time
import httpx
import os

app = FastAPI(title="tools-service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ToolExecRequest(BaseModel):
    name: str
    args: Dict[str, Any] = {}

class ToolExecResponse(BaseModel):
    success: bool
    output: str
    execution_time_ms: int

async def scrape_webpage(url: str) -> str:
    """Scrape a webpage using FIRECRAWL API"""
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
    
    if not firecrawl_api_key:
        raise ValueError("FIRECRAWL_API_KEY not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {firecrawl_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "url": url,
                "formats": ["markdown", "html"],
                "onlyMainContent": True
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("markdown", "No content found")
        else:
            raise Exception(f"FIRECRAWL API error: {response.status_code} - {response.text}")

async def search_web(query: str) -> str:
    """Search the web using FIRECRAWL API"""
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
    
    if not firecrawl_api_key:
        raise ValueError("FIRECRAWL_API_KEY not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/search",
            headers={
                "Authorization": f"Bearer {firecrawl_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "limit": 5,
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True
                }
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", [])
            if results:
                # Combine the top results
                combined_content = ""
                for i, result in enumerate(results[:3]):  # Take top 3 results
                    title = result.get("title", "")
                    content = result.get("markdown", "")
                    url = result.get("url", "")
                    combined_content += f"\n\n--- Result {i+1}: {title} ---\n"
                    combined_content += f"URL: {url}\n"
                    combined_content += f"Content: {content[:500]}...\n"
                return combined_content
            else:
                return "No search results found"
        else:
            raise Exception(f"FIRECRAWL Search API error: {response.status_code} - {response.text}")

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "tools-service"}

@app.post("/v1/tools/exec", response_model=ToolExecResponse)
async def exec_tool(request: ToolExecRequest):
    """Execute a tool with given arguments"""
    start_time = time.time()
    
    try:
        # Simple echo tool implementation
        if request.name == "echo":
            output = request.args.get("text", "hello")
        elif request.name == "add":
            a = request.args.get("a", 0)
            b = request.args.get("b", 0)
            output = str(a + b)
        elif request.name == "web_scrape":
            url = request.args.get("url")
            if not url:
                raise ValueError("URL is required for web_scrape tool")
            output = await scrape_webpage(url)
        elif request.name == "web_search":
            query = request.args.get("query")
            if not query:
                raise ValueError("Query is required for web_search tool")
            output = await search_web(query)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.name}")
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolExecResponse(
            success=True,
            output=output,
            execution_time_ms=execution_time
        )
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        return ToolExecResponse(
            success=False,
            output=f"Error: {str(e)}",
            execution_time_ms=execution_time
        )

@app.get("/v1/tools")
def list_tools():
    """List available tools"""
    return {
        "tools": [
            {"name": "echo", "description": "Echo back text"},
            {"name": "add", "description": "Add two numbers"},
            {"name": "web_scrape", "description": "Scrape content from a webpage using FIRECRAWL API", "args": {"url": "string"}},
            {"name": "web_search", "description": "Search the web using FIRECRAWL API", "args": {"query": "string"}}
        ]
    }
