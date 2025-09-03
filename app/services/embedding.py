"""
임베딩 생성 서비스
"""

from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

settings = get_settings()


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.embedding_model)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트를 임베딩으로 변환"""
        embedding = self.model.encode(text)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 임베딩으로 변환"""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """쿼리 텍스트를 임베딩으로 변환 (langchain 호환)"""
        return self.embed_text(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """문서들을 임베딩으로 변환 (langchain 호환)"""
        return self.embed_texts(texts)

    def get_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self.dimension


# 전역 임베딩 서비스 인스턴스
embedding_service = EmbeddingService()
