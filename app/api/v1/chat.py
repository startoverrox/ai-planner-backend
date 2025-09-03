"""
채팅 API 엔드포인트
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag import rag_service

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    k: int = 5  # 검색할 문서 수


class SourceInfo(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int
    content_preview: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    query: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG 기반 채팅 API

    - **query**: 질문 내용
    - **k**: 검색할 관련 문서 수 (기본값: 5)
    """
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

        # RAG 서비스를 통해 답변 생성
        result = rag_service.answer_question(request.query, request.k)

        # 응답 모델에 맞게 변환
        sources = [
            SourceInfo(
                chunk_id=source.get("chunk_id", ""),
                document_id=source.get("document_id", ""),
                page_number=source.get("page_number", 0),
                content_preview=source.get("content_preview", ""),
            )
            for source in result["sources"]
        ]

        return ChatResponse(
            answer=result["answer"], sources=sources, query=request.query
        )

    except Exception as e:
        print(f"채팅 API 오류: {e}")
        raise HTTPException(
            status_code=500, detail="내부 서버 오류가 발생했습니다."
        )


@router.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트
    """
    return {"status": "healthy", "service": "chat"}
