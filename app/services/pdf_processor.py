"""
PDF 문서 처리 및 청킹 서비스
"""

import io
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Union

from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.documents import Document, DocumentChunk
from app.services.embedding import embedding_service
from app.services.storage import storage_service

settings = get_settings()


class PDFProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def extract_text_from_pdf(
        self, file_data: Union[str, BinaryIO, io.BytesIO]
    ) -> List[Dict[str, Any]]:
        """PDF에서 텍스트 추출 (파일 경로 또는 파일 데이터)"""
        try:
            reader = PdfReader(file_data)
            pages_text = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    pages_text.append(
                        {"page_number": page_num, "text": text.strip()}
                    )

            return pages_text
        except Exception as e:
            print(f"PDF 처리 중 오류 발생: {e}")
            return []

    def create_chunks(
        self, pages_text: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """텍스트를 청크로 분할"""
        chunks = []
        chunk_index = 0

        for page_data in pages_text:
            page_number = page_data["page_number"]
            text = page_data["text"]

            # 페이지 텍스트를 청크로 분할
            page_chunks = self.text_splitter.split_text(text)

            for chunk_text in page_chunks:
                if chunk_text.strip():
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "content": chunk_text.strip(),
                            "page_number": page_number,
                        }
                    )
                    chunk_index += 1

        return chunks

    def process_pdf_from_storage(self, object_name: str, db: Session) -> str:
        """MinIO에서 PDF 다운로드 후 처리"""
        try:
            # MinIO에서 파일 다운로드
            file_data = storage_service.download_file(object_name)
            if not file_data:
                raise FileNotFoundError(
                    f"MinIO에서 파일을 찾을 수 없습니다: {object_name}"
                )

            # 파일 크기 계산
            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)

            # 문서 레코드 생성
            document = Document(
                filename=object_name,
                file_path=f"minio://{storage_service.bucket_name}/{object_name}",
                file_size=file_size,
                status="processing",
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # PDF에서 텍스트 추출
            pages_text = self.extract_text_from_pdf(file_data)
            if not pages_text:
                document.status = "error"
                db.commit()
                return str(document.id)

            # 텍스트를 청크로 분할
            chunks = self.create_chunks(pages_text)

            # 청크를 데이터베이스에 저장
            for chunk_data in chunks:
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    page_number=chunk_data["page_number"],
                )
                db.add(chunk)

            # 처리 완료 상태 업데이트
            document.status = "completed"
            db.commit()

            return str(document.id)

        except Exception as e:
            print(f"PDF 처리 중 오류 발생: {e}")
            if "document" in locals():
                document.status = "error"
                db.commit()
            raise e

    def process_pdf_from_upload(
        self, file_data: BinaryIO, filename: str, db: Session
    ) -> str:
        """업로드된 파일을 MinIO에 저장 후 처리"""
        try:
            # 고유한 object name 생성
            file_extension = Path(filename).suffix
            object_name = f"{uuid.uuid4()}{file_extension}"

            # MinIO에 파일 업로드
            if not storage_service.upload_file(file_data, object_name):
                raise Exception("파일 업로드 실패")

            # 업로드된 파일 처리
            return self.process_pdf_from_storage(object_name, db)

        except Exception as e:
            print(f"파일 업로드 및 처리 중 오류 발생: {e}")
            raise e


# 전역 PDF 프로세서 인스턴스
pdf_processor = PDFProcessor()
