from pydantic_settings import BaseSettings
from os import getenv

class Settings(BaseSettings):
    redis_host: str = getenv('REDIS_HOST', "localhost")
    redis_port: int = int(getenv("REDIS_PORT", 6379))
    db_path: str = getenv("DB_PATH", "data/students_profiles.db")

    llm_base_url: str = getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_model: str = getenv("LLM_MODEL", "llama3:8b")
    llm_api_key: str = getenv("LLM_API_KEY", "ollama")
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }