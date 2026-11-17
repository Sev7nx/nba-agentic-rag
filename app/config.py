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
    docs_path: str = "data/docs/documents.jsonl"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_local_only: bool = True
    rerank_model: str = "BAAI/bge-reranker-base"
    rerank_enabled: bool = False
    api_url: str = "http://localhost:8000"
    rate_limit: str = "20/hour"


settings = Settings()