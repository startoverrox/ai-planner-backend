"""
RAG (Retrieval-Augmented Generation) 서비스
"""

from typing import Any, Dict, List

import ollama
from langchain.schema import Document as LangchainDocument

from app.core.config import get_settings
from app.services.vector_store import vector_store_service

settings = get_settings()


class RAGService:
    def __init__(self):
        self.ollama_client = ollama.Client(host=settings.ollama_base_url)
        self.model_name = settings.ollama_model
        self.vector_store = vector_store_service

    def retrieve_relevant_documents(
        self, query: str, k: int = 5
    ) -> List[LangchainDocument]:
        """관련 문서 검색"""
        try:
            # 벡터 스토어에서 유사도 검색
            relevant_docs = self.vector_store.similarity_search(query, k=k)
            return relevant_docs

        except Exception as e:
            print(f"문서 검색 중 오류 발생: {e}")
            return []

    def generate_context(self, documents: List[LangchainDocument]) -> str:
        """검색된 문서들로부터 컨텍스트 생성"""
        context_parts = []

        for i, doc in enumerate(documents, 1):
            content = doc.page_content
            metadata = doc.metadata

            context_part = f"[문서 {i}]\n"
            if metadata.get("page_number"):
                context_part += f"(페이지 {metadata['page_number']})\n"
            context_part += f"{content}\n\n"

            context_parts.append(context_part)

        return "".join(context_parts)

    def create_prompt(self, query: str, context: str) -> str:
        """RAG 프롬프트 생성"""
        prompt = f"""다음 문서들을 바탕으로 질문에 답변해주세요. 문서에 없는 내용은 추측하지 말고, 문서 기반으로만 답변해주세요.

관련 문서:
{context}

질문: {query}

답변:"""
        return prompt

    def generate_response(self, prompt: str) -> str:
        """Ollama를 사용한 응답 생성"""
        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )

            return response["message"]["content"]

        except Exception as e:
            print(f"Ollama 응답 생성 중 오류 발생: {e}")
            return "죄송합니다. 현재 응답을 생성할 수 없습니다. 나중에 다시 시도해주세요."

    def answer_question(self, query: str, k: int = 5) -> Dict[str, Any]:
        """RAG 파이프라인 - 질문에 대한 답변 생성"""
        try:
            # 1. 관련 문서 검색
            relevant_docs = self.retrieve_relevant_documents(query, k=k)

            if not relevant_docs:
                return {
                    "answer": "관련된 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                    "sources": [],
                    "context": "",
                }

            # 2. 컨텍스트 생성
            context = self.generate_context(relevant_docs)

            # 3. 프롬프트 생성
            prompt = self.create_prompt(query, context)

            # 4. 응답 생성
            answer = self.generate_response(prompt)

            # 5. 소스 정보 준비
            sources = []
            for doc in relevant_docs:
                metadata = doc.metadata
                source_info = {
                    "chunk_id": metadata.get("chunk_id"),
                    "document_id": metadata.get("document_id"),
                    "page_number": metadata.get("page_number"),
                    "content_preview": doc.page_content[:200] + "..."
                    if len(doc.page_content) > 200
                    else doc.page_content,
                }
                sources.append(source_info)

            return {"answer": answer, "sources": sources, "context": context}

        except Exception as e:
            print(f"RAG 질문 답변 중 오류 발생: {e}")
            return {
                "answer": "죄송합니다. 질문 처리 중 오류가 발생했습니다.",
                "sources": [],
                "context": "",
            }


# 전역 RAG 서비스 인스턴스
rag_service = RAGService()
