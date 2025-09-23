from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "retrieval-service"
    host: str = "0.0.0.0"
    port: int = 8080
    enable_cors: bool = True
    allowed_origins: str | None = "*"
    # backing stores (placeholders)
    vector_db_url: str | None = None
    keyword_index_url: str | None = None
    reranker_endpoint: str | None = None

    class Config:
        env_prefix = "RETRIEVAL_"


settings = Settings()

