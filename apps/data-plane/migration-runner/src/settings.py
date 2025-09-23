from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "migration-runner"
    host: str = "0.0.0.0"
    port: int = 8071
    class Config:
        env_prefix = "MR_"

settings = Settings()

