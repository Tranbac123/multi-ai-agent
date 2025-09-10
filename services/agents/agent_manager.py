"""Agent management service."""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Agent:
    """Agent configuration."""
    agent_id: str
    name: str
    description: str
    capabilities: List[str]
    status: str = "active"


class AgentManager:
    """Manages agent lifecycle and configuration."""
    
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
    
    def register_agent(self, agent: Agent) -> None:
        """Register a new agent."""
        self._agents[agent.agent_id] = agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> List[Agent]:
        """List all agents."""
        return list(self._agents.values())
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status."""
        if agent_id in self._agents:
            self._agents[agent_id].status = status
            return True
        return False
