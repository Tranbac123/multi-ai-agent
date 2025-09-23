from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "event-relay-service"
    host: str = "0.0.0.0" 
    port: int = 8072
    nats_url: str = "nats://nats:4222"
    stream: str = "platform"
    webhook_concurrency: int = 16
    hmac_secret: str = "change-me"
    class Config:
        env_prefix = "ERS_"

settings = Settings()

