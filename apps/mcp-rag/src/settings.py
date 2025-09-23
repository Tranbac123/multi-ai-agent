from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "mcp-rag"
    host: str = "0.0.0.0"
    port: int = 8765
    retrieval_base_url: str = "http://retrieval-service"
    ingestion_base_url: str = "http://ingestion-service"

    class Config:
        env_prefix = "MCP_RAG_"


settings = Settings()

