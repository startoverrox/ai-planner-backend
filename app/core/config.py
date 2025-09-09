"""
애플리케이션 설정 관리
"""

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # 데이터베이스 설정
    database_url: str = Field(env="DATABASE_URL")

    # MinIO 설정
    minio_endpoint: str = Field(env="MINIO_ENDPOINT")
    minio_access_key: str = Field(env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(env="MINIO_SECRET_KEY")
    minio_root_user: str = Field(env="MINIO_ROOT_USER")
    minio_root_password: str = Field(env="MINIO_ROOT_PASSWORD")
    minio_bucket: str = Field(env="MINIO_BUCKET")
    minio_secure: bool = Field(env="MINIO_SECURE")

    # AWS 설정
    aws_region: str = Field(env="AWS_REGION")
    aws_access_key_id: str = Field(env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(env="AWS_SECRET_ACCESS_KEY")

    # Ollama 설정
    ollama_base_url: str = Field(env="OLLAMA_BASE_URL")
    ollama_model: str = Field(env="OLLAMA_MODEL")

    # FastAPI 설정
    api_v1_str: str = "/api/v1"
    project_name: str = Field(env="PROJECT_NAME")
    debug: bool = Field(env="DEBUG")

    # 임베딩 모델 설정
    embedding_model: str = Field(env="EMBEDDING_MODEL")

    # 청킹 설정
    chunk_size: int = Field(env="CHUNK_SIZE")
    chunk_overlap: int = Field(env="CHUNK_OVERLAP")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
