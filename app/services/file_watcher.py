"""
파일 감시 및 자동 처리 서비스 (백업용)
"""

import asyncio
import time
from typing import Set

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.documents import Document
from app.services.pdf_processor import pdf_processor
from app.services.storage import storage_service
from app.services.vector_store import vector_store_service


class FileWatcherService:
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval  # 초 단위
        self.processed_files: Set[str] = set()
        self.running = False

    async def start_watching(self):
        """파일 감시 시작"""
        self.running = True
        print(f"File Watcher 시작 (체크 간격: {self.check_interval}초)")

        # 기존 처리된 파일들 로드
        await self._load_processed_files()

        while self.running:
            try:
                await self._check_new_files()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"File Watcher 오류: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_watching(self):
        """파일 감시 중지"""
        self.running = False
        print("File Watcher 중지됨")

    async def _load_processed_files(self):
        """데이터베이스에서 이미 처리된 파일 목록 로드"""
        try:
            db = SessionLocal()

            # MinIO 경로가 포함된 문서들 조회
            documents = (
                db.query(Document)
                .filter(Document.file_path.like("minio://%"))
                .all()
            )

            for doc in documents:
                # file_path에서 object_name 추출
                if "/" in doc.file_path:
                    object_name = doc.file_path.split("/")[-1]
                    self.processed_files.add(object_name)

            db.close()
            print(f"기존 처리된 파일 {len(self.processed_files)}개 로드됨")

        except Exception as e:
            print(f"처리된 파일 로드 오류: {e}")

    async def _check_new_files(self):
        """새로운 파일 확인 및 처리"""
        try:
            # MinIO에서 PDF 파일 목록 조회
            all_files = storage_service.list_files()
            pdf_files = [f for f in all_files if f.endswith(".pdf")]

            # 새로운 파일 찾기
            new_files = [f for f in pdf_files if f not in self.processed_files]

            if new_files:
                print(f"새로운 파일 {len(new_files)}개 발견: {new_files}")

                for file_name in new_files:
                    await self._process_new_file(file_name)

        except Exception as e:
            print(f"새 파일 확인 오류: {e}")

    async def _process_new_file(self, object_name: str):
        """새 파일 처리"""
        try:
            print(f"File Watcher에서 처리 시작: {object_name}")

            db = SessionLocal()

            # 이미 처리 중인지 다시 확인
            existing_doc = (
                db.query(Document)
                .filter(Document.file_path.like(f"%{object_name}"))
                .first()
            )

            if existing_doc:
                print(f"이미 처리된 파일입니다: {object_name}")
                self.processed_files.add(object_name)
                db.close()
                return

            # PDF 처리
            document_id = pdf_processor.process_pdf_from_storage(
                object_name, db
            )

            # 벡터 스토어에 추가
            vector_store_service.add_document_chunks(db, document_id)

            # 처리 완료 표시
            self.processed_files.add(object_name)

            db.close()
            print(
                f"File Watcher에서 처리 완료: {object_name} (문서 ID: {document_id})"
            )

        except Exception as e:
            print(f"File Watcher 파일 처리 오류 ({object_name}): {e}")
            if "db" in locals():
                db.close()

    def add_processed_file(self, object_name: str):
        """처리 완료된 파일을 목록에 추가 (중복 처리 방지)"""
        self.processed_files.add(object_name)


# 전역 File Watcher 인스턴스
file_watcher_service = FileWatcherService()
