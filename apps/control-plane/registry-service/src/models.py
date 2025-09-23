from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class AgentManifest(BaseModel):
    name: str
    version: str
    checksum_sha256: str
    owner: str
    deprecated: bool = False
    metadata: Dict[str, Any] = {}
    signature: Optional[str] = None

class ToolManifest(BaseModel):
    name: str
    version: str
    checksum_sha256: str
    owner: str
    deprecated: bool = False
    metadata: Dict[str, Any] = {}
    signature: Optional[str] = None

