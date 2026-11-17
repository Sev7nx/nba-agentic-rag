from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    tavily_api_key: str = ""
    chroma_dir: str = "data/chroma"
    cache_path: str = "data/cache.db"
    profile_path: str = "data/profile.json"
    stats_db_path: str = "data/stats.sqlite"
    stats_as_of: str = "2026-11-01"
    api_url: str = "http://localhost:8000"
    rate_limit: str = "20/hour"


settings = Settings()