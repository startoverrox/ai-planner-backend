"""
Langchain PostgreSQL Vector Store 서비스
"""

from typing import Any, Dict, List, Optional

from langchain.schema import Document as LangchainDocument
from langchain_postgres.vectorstores import PGVector
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.documents import DocumentChunk
from app.services.embedding import embedding_service

settings = get_settings()


class VectorStoreService:
    def __init__(self):
        # PGVector 설정
        self.connection_string = settings.database_url
        self.collection_name = "document_embeddings"
        self.embedding_function = embedding_service

        # PGVector 인스턴스 생성 (새로운 API)
        self.vector_store = PGVector(
            embeddings=self.embedding_function,
            connection=self.connection_string,
            collection_name=self.collection_name,
        )

    def add_document_chunks(self, db: Session, document_id: str):
        """문서 청크들을 벡터 스토어에 추가"""
        try:
            # 문서 청크 조회
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .all()
            )

            if not chunks:
                print(f"문서 ID {document_id}에 대한 청크를 찾을 수 없습니다.")
                return

            # Langchain Document 객체로 변환
            documents = []
            for chunk in chunks:
                doc = LangchainDocument(
                    page_content=chunk.content,
                    metadata={
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                    },
                )
                documents.append(doc)

            # 벡터 스토어에 추가
            self.vector_store.add_documents(documents)
            print(
                f"문서 ID {document_id}의 {len(documents)}개 청크를 벡터 스토어에 추가했습니다."
            )

        except Exception as e:
            print(f"벡터 스토어에 청크 추가 중 오류 발생: {e}")
            raise e

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[LangchainDocument]:
        """유사도 검색"""
        try:
            if filter_dict:
                results = self.vector_store.similarity_search(
                    query, k=k, filter=filter_dict
                )
            else:
                results = self.vector_store.similarity_search(query, k=k)

            return results

        except Exception as e:
            print(f"유사도 검색 중 오류 발생: {e}")
            return []

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[tuple]:
        """유사도 검색 (점수 포함)"""
        try:
            if filter_dict:
                results = self.vector_store.similarity_search_with_score(
                    query, k=k, filter=filter_dict
                )
            else:
                results = self.vector_store.similarity_search_with_score(
                    query, k=k
                )

            return results

        except Exception as e:
            print(f"유사도 검색 중 오류 발생: {e}")
            return []

    def delete_document(self, document_id: str):
        """문서 삭제 (벡터 스토어에서)"""
        try:
            # 메타데이터로 필터링하여 삭제
            filter_dict = {"document_id": document_id}
            self.vector_store.delete(filter=filter_dict)
            print(f"문서 ID {document_id}를 벡터 스토어에서 삭제했습니다.")

        except Exception as e:
            print(f"벡터 스토어에서 문서 삭제 중 오류 발생: {e}")
            raise e


# 전역 벡터 스토어 서비스 인스턴스
vector_store_service = VectorStoreService()
