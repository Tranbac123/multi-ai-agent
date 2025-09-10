"""Memory management service."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time


@dataclass
class MemoryItem:
    """Memory item structure."""
    key: str
    value: Any
    timestamp: float
    ttl: Optional[int] = None


class MemoryManager:
    """Manages memory and knowledge storage."""
    
    def __init__(self):
        self._memory: Dict[str, MemoryItem] = {}
    
    def store(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a memory item."""
        self._memory[key] = MemoryItem(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl
        )
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a memory item."""
        item = self._memory.get(key)
        if item is None:
            return None
        
        # Check TTL
        if item.ttl and time.time() - item.timestamp > item.ttl:
            del self._memory[key]
            return None
        
        return item.value
    
    def delete(self, key: str) -> bool:
        """Delete a memory item."""
        if key in self._memory:
            del self._memory[key]
            return True
        return False
    
    def list_keys(self) -> List[str]:
        """List all memory keys."""
        return list(self._memory.keys())
    
    def clear(self) -> None:
        """Clear all memory."""
        self._memory.clear()
