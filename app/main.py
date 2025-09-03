"""
FastAPI 메인 애플리케이션
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, documents
from app.core.config import get_settings
from app.db.database import init_db
from app.services.cleanup import cleanup_orphaned_data_on_startup
from app.services.file_watcher import file_watcher_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 실행
    print("애플리케이션 시작...")

    # 데이터베이스 초기화
    try:
        init_db()
        print("데이터베이스 초기화 완료")
    except Exception as e:
        print(f"데이터베이스 초기화 오류: {e}")

    # Orphaned 데이터 정리 (시작 시 자동 실행)
    try:
        cleanup_orphaned_data_on_startup()
    except Exception as e:
        print(f"Orphaned 데이터 정리 오류: {e}")

    # File Watcher 백그라운드 태스크 시작
    watcher_task = None
    try:
        watcher_task = asyncio.create_task(
            file_watcher_service.start_watching()
        )
        print("File Watcher 백그라운드 태스크 시작")
    except Exception as e:
        print(f"File Watcher 시작 오류: {e}")

    yield

    # 종료 시 실행
    print("애플리케이션 종료...")

    # File Watcher 정리
    if watcher_task:
        file_watcher_service.stop_watching()
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            print("File Watcher 태스크 정리 완료")
        except Exception as e:
            print(f"File Watcher 정리 오류: {e}")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.project_name,
    description="AI Planner Backend - RAG 기반 문서 질의응답 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(chat.router, prefix=settings.api_v1_str, tags=["chat"])

app.include_router(
    documents.router, prefix=settings.api_v1_str, tags=["documents"]
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "AI Planner Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy", "service": "ai-planner-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=settings.debug
    )
