from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"


    # Classifier
    classifier_model: str = "facebook/bart-large-mnli"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Syslog receiver (non-privileged port — no admin rights needed)
    syslog_port: int = 5140

    # Database
    database_url: str = "sqlite+aiosqlite:///./agentsoc.db"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()