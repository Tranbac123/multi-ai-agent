from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import time

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

@app.get("/healthz")
def healthz():
    return {"ok": True, "name": "tools-service"}

@app.post("/v1/tools/exec", response_model=ToolExecResponse)
def exec_tool(request: ToolExecRequest):
    """Execute a tool with given arguments"""
    start_time = time.time()
    
    # Simple echo tool implementation
    if request.name == "echo":
        output = request.args.get("text", "hello")
    elif request.name == "add":
        a = request.args.get("a", 0)
        b = request.args.get("b", 0)
        output = str(a + b)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {request.name}")
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return ToolExecResponse(
        success=True,
        output=output,
        execution_time_ms=execution_time
    )

@app.get("/v1/tools")
def list_tools():
    """List available tools"""
    return {
        "tools": [
            {"name": "echo", "description": "Echo back text"},
            {"name": "add", "description": "Add two numbers"}
        ]
    }
