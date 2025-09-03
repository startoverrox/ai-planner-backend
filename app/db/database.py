"""
데이터베이스 연결 및 세션 관리
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.database_url, pool_pre_ping=True, echo=settings.debug
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()


def get_db() -> Session:
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """데이터베이스 초기화"""
    # pgvector 확장 설치 확인
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        if not result.fetchone():
            conn.execute(text("CREATE EXTENSION vector"))
            conn.commit()

    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
