"""
애플리케이션 설정 관리
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 데이터베이스 설정
    database_url: str = (
        "postgresql+psycopg://postgres:password@localhost:5432/ai_planner"
    )

    # Ollama 설정
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # FastAPI 설정
    api_v1_str: str = "/api/v1"
    project_name: str = "AI Planner Backend"
    debug: bool = True

    # 임베딩 모델 설정
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # 청킹 설정
    chunk_size: int = 1000
    chunk_overlap: int = 200

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
