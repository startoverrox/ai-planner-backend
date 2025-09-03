"""
문서 처리 API 엔드포인트
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.documents import Document, DocumentChunk
from app.services.cleanup import (
    cleanup_orphaned_data_on_startup,
    get_sync_status,
)
from app.services.file_watcher import file_watcher_service
from app.services.pdf_processor import pdf_processor
from app.services.storage import storage_service
from app.services.vector_store import vector_store_service

router = APIRouter()


class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_size: int
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int


def process_document_background(file_path: str, document_id: str):
    """백그라운드에서 문서 처리 및 벡터화"""
    try:
        # 새로운 데이터베이스 세션 생성
        from app.db.database import SessionLocal

        db = SessionLocal()

        # 벡터 스토어에 추가
        vector_store_service.add_document_chunks(db, document_id)

        db.close()
        print(f"문서 {document_id} 벡터화 완료")

    except Exception as e:
        print(f"백그라운드 문서 처리 오류: {e}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    문서 목록 조회

    - **skip**: 건너뛸 문서 수
    - **limit**: 반환할 최대 문서 수
    """
    try:
        # 전체 문서 수 조회
        total = db.query(Document).count()

        # 문서 목록 조회
        documents = db.query(Document).offset(skip).limit(limit).all()

        document_list = [
            DocumentInfo(
                id=str(doc.id),
                filename=doc.filename,
                file_size=doc.file_size or 0,
                status=doc.status,
                created_at=doc.created_at,
                processed_at=doc.processed_at,
            )
            for doc in documents
        ]

        return DocumentListResponse(documents=document_list, total=total)

    except Exception as e:
        print(f"문서 목록 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail="문서 목록 조회 중 오류 발생"
        )


@router.get("/documents/{document_id}")
async def get_document_detail(document_id: str, db: Session = Depends(get_db)):
    """
    문서 상세 정보 조회
    """
    try:
        # 문서 조회
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=404, detail="문서를 찾을 수 없습니다."
            )

        # 청크 수 조회
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .count()
        )

        return {
            "id": str(document.id),
            "filename": document.filename,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "status": document.status,
            "created_at": document.created_at,
            "processed_at": document.processed_at,
            "chunk_count": chunk_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"문서 상세 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail="문서 상세 조회 중 오류 발생"
        )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """
    문서 삭제 (데이터베이스 및 벡터 스토어에서)
    """
    try:
        # 문서 조회
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=404, detail="문서를 찾을 수 없습니다."
            )

        # 벡터 스토어에서 삭제
        vector_store_service.delete_document(document_id)

        # 데이터베이스에서 청크 삭제
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete()

        # 문서 삭제
        db.delete(document)
        db.commit()

        return {"message": "문서가 성공적으로 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        print(f"문서 삭제 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="문서 삭제 중 오류 발생")


@router.post("/documents/upload")
async def upload_pdf_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    PDF 파일 업로드 및 처리

    - **file**: 업로드할 PDF 파일
    """
    try:
        # 파일 형식 검증
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="PDF 파일만 업로드 가능합니다."
            )

        # 파일 크기 제한 (예: 50MB)
        file_content = await file.read()
        if len(file_content) > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(
                status_code=400, detail="파일 크기는 50MB를 초과할 수 없습니다."
            )

        # 이미 처리된 문서인지 확인 (파일명 기준)
        existing_doc = (
            db.query(Document)
            .filter(Document.filename == file.filename)
            .first()
        )

        if existing_doc:
            return {
                "message": "이미 처리된 문서입니다.",
                "document_id": str(existing_doc.id),
                "status": existing_doc.status,
            }

        # 파일을 MinIO에 업로드하고 처리
        import io

        file_stream = io.BytesIO(file_content)
        document_id = pdf_processor.process_pdf_from_upload(
            file_stream, file.filename, db
        )

        # 백그라운드에서 벡터화 작업 수행
        background_tasks.add_task(
            process_document_background,
            None,  # 파일 경로가 아닌 storage에서 처리
            document_id,
        )

        return {
            "message": "파일 업로드 및 처리를 시작했습니다.",
            "document_id": document_id,
            "status": "processing",
            "filename": file.filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"파일 업로드 API 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"파일 업로드 중 오류 발생: {str(e)}"
        )


@router.post("/documents/process-from-storage")
async def process_pdf_from_storage(
    object_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    MinIO Storage에서 PDF 문서 처리

    - **object_name**: MinIO에 저장된 파일의 object name
    """
    try:
        # MinIO에서 파일 존재 확인
        if not storage_service.file_exists(object_name):
            raise HTTPException(
                status_code=404,
                detail=f"MinIO에서 파일을 찾을 수 없습니다: {object_name}",
            )

        # 이미 처리된 문서인지 확인
        existing_doc = (
            db.query(Document)
            .filter(Document.file_path.like(f"%{object_name}"))
            .first()
        )

        if existing_doc:
            return {
                "message": "이미 처리된 문서입니다.",
                "document_id": str(existing_doc.id),
                "status": existing_doc.status,
            }

        # PDF 처리 (청킹까지)
        document_id = pdf_processor.process_pdf_from_storage(object_name, db)

        # 백그라운드에서 벡터화 작업 수행
        background_tasks.add_task(
            process_document_background, None, document_id
        )

        return {
            "message": "문서 처리를 시작했습니다.",
            "document_id": document_id,
            "status": "processing",
            "object_name": object_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Storage 문서 처리 API 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"문서 처리 중 오류 발생: {str(e)}"
        )


@router.get("/storage/files")
async def list_storage_files():
    """
    MinIO Storage에 저장된 파일 목록 조회
    """
    try:
        files = storage_service.list_files()
        pdf_files = [f for f in files if f.endswith(".pdf")]

        return {"files": pdf_files, "total": len(pdf_files)}

    except Exception as e:
        print(f"Storage 파일 목록 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail="파일 목록 조회 중 오류 발생"
        )


@router.get("/storage/files/{object_name}/url")
async def get_file_download_url(object_name: str, expires_seconds: int = 3600):
    """
    MinIO Storage 파일의 임시 다운로드 URL 생성

    - **object_name**: 파일의 object name
    - **expires_seconds**: URL 만료 시간 (초, 기본값: 1시간)
    """
    try:
        if not storage_service.file_exists(object_name):
            raise HTTPException(
                status_code=404, detail="파일을 찾을 수 없습니다."
            )

        url = storage_service.get_file_url(object_name, expires_seconds)
        if not url:
            raise HTTPException(status_code=500, detail="URL 생성 실패")

        return {
            "download_url": url,
            "expires_in": expires_seconds,
            "object_name": object_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"파일 URL 생성 오류: {e}")
        raise HTTPException(status_code=500, detail="URL 생성 중 오류 발생")


# MinIO Event Notification Models
class MinIOEventRecord(BaseModel):
    eventVersion: str
    eventSource: str
    eventName: str
    eventTime: str
    s3: dict


class MinIOWebhookPayload(BaseModel):
    Records: List[MinIOEventRecord]


@router.post("/minio/webhook")
async def handle_minio_webhook(
    payload: MinIOWebhookPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    MinIO Event Notification 웹훅 처리

    파일 업로드/삭제 시 자동으로 DB 동기화를 처리합니다.
    """
    try:
        processed_files = []
        deleted_files = []

        for record in payload.Records:
            event_name = record.eventName

            # S3 정보에서 파일 정보 추출
            s3_info = record.s3
            object_info = s3_info.get("object", {})
            object_name = object_info.get("key", "")

            # PDF 파일만 처리
            if not object_name.lower().endswith(".pdf"):
                continue

            # 파일 생성 이벤트 처리
            if event_name.startswith("s3:ObjectCreated:"):
                # 이미 처리 중인지 확인
                existing_doc = (
                    db.query(Document)
                    .filter(Document.file_path.like(f"%{object_name}"))
                    .first()
                )

                if existing_doc:
                    print(f"이미 처리된 파일입니다: {object_name}")
                    continue

                print(f"새 PDF 파일 감지: {object_name} (이벤트: {event_name})")

                # 백그라운드에서 처리
                background_tasks.add_task(process_pdf_from_webhook, object_name, db)
                processed_files.append(object_name)

            # 파일 삭제 이벤트 처리
            elif event_name.startswith("s3:ObjectRemoved:"):
                print(f"PDF 파일 삭제 감지: {object_name} (이벤트: {event_name})")

                # 백그라운드에서 삭제 처리
                background_tasks.add_task(delete_file_from_webhook, object_name)
                deleted_files.append(object_name)

        response_message = []
        if processed_files:
            response_message.append(f"{len(processed_files)}개 파일 처리 시작")
        if deleted_files:
            response_message.append(f"{len(deleted_files)}개 파일 삭제 처리 시작")

        return {
            "message": ", ".join(response_message) if response_message else "처리할 파일이 없습니다",
            "processed_files": processed_files,
            "deleted_files": deleted_files,
        }

    except Exception as e:
        print(f"MinIO 웹훅 처리 오류: {e}")
        # 웹훅은 실패해도 200을 반환해야 MinIO가 재시도하지 않음
        return {"error": str(e), "status": "failed"}


async def process_pdf_from_webhook(object_name: str, db: Session):
    """웹훅에서 호출되는 PDF 처리 함수"""
    try:
        # 새로운 데이터베이스 세션 생성
        from app.db.database import SessionLocal

        new_db = SessionLocal()

        # PDF 처리 (청킹까지)
        print(f"웹훅에서 PDF 처리 시작: {object_name}")
        document_id = pdf_processor.process_pdf_from_storage(
            object_name, new_db
        )

        # 벡터 스토어에 추가
        vector_store_service.add_document_chunks(new_db, document_id)

        # File Watcher의 처리 목록에 추가 (중복 처리 방지)
        file_watcher_service.add_processed_file(object_name)

        new_db.close()
        print(f"웹훅에서 PDF 처리 완료: {object_name} (문서 ID: {document_id})")

    except Exception as e:
        print(f"웹훅 PDF 처리 오류 ({object_name}): {e}")
        if "new_db" in locals():
            new_db.close()


async def delete_file_from_webhook(object_name: str):
    """웹훅에서 호출되는 파일 삭제 처리 함수"""
    try:
        # 새로운 데이터베이스 세션 생성
        from app.db.database import SessionLocal

        new_db = SessionLocal()

        print(f"웹훅에서 파일 삭제 처리 시작: {object_name}")

        # file_path로 문서 찾기
        documents = (
            new_db.query(Document)
            .filter(Document.file_path.like(f"%{object_name}"))
            .all()
        )

        if not documents:
            print(f"삭제할 문서를 찾을 수 없습니다: {object_name}")
            new_db.close()
            return

        deleted_count = 0
        for document in documents:
            document_id = str(document.id)

            # 벡터 스토어에서 삭제
            try:
                vector_store_service.delete_document(document_id)
                print(f"벡터 스토어에서 문서 삭제 완료: {document_id}")
            except Exception as e:
                print(f"벡터 스토어 삭제 오류 ({document_id}): {e}")

            # 데이터베이스에서 청크 삭제
            chunks_deleted = new_db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete()

            # 문서 삭제
            new_db.delete(document)
            deleted_count += 1

            print(f"DB에서 문서 삭제 완료: {document.filename} (청크 {chunks_deleted}개)")

        # File Watcher의 처리 목록에서 제거
        if object_name in file_watcher_service.processed_files:
            file_watcher_service.processed_files.remove(object_name)

        new_db.commit()
        new_db.close()

        print(f"웹훅에서 파일 삭제 처리 완료: {object_name} ({deleted_count}개 문서 삭제)")

    except Exception as e:
        print(f"웹훅 파일 삭제 처리 오류 ({object_name}): {e}")
        if "new_db" in locals():
            new_db.rollback()
            new_db.close()


@router.get("/file-watcher/status")
async def get_file_watcher_status():
    """
    File Watcher 상태 조회
    """
    return {
        "running": file_watcher_service.running,
        "check_interval": file_watcher_service.check_interval,
        "processed_files_count": len(file_watcher_service.processed_files),
        "last_check": "실시간 모니터링 중"
        if file_watcher_service.running
        else "중지됨",
    }


@router.post("/file-watcher/force-check")
async def force_file_watcher_check():
    """
    File Watcher 강제 실행 (수동 트리거)
    """
    try:
        if not file_watcher_service.running:
            return {
                "message": "File Watcher가 실행 중이 아닙니다.",
                "status": "stopped",
            }

        # 강제로 새 파일 확인 실행
        await file_watcher_service._check_new_files()

        return {
            "message": "File Watcher 강제 실행 완료",
            "processed_files_count": len(file_watcher_service.processed_files),
        }

    except Exception as e:
        print(f"File Watcher 강제 실행 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"강제 실행 중 오류 발생: {str(e)}"
        )


@router.get("/auto-processing/test")
async def test_auto_processing():
    """
    자동 처리 시스템 테스트

    MinIO에 있는 미처리 파일들을 확인하고 처리 상태를 보고합니다.
    """
    try:
        db = SessionLocal()

        # MinIO의 모든 PDF 파일 조회
        all_files = storage_service.list_files()
        pdf_files = [f for f in all_files if f.endswith(".pdf")]

        # 데이터베이스에서 처리된 파일들 조회
        processed_docs = (
            db.query(Document)
            .filter(Document.file_path.like("minio://%"))
            .all()
        )

        processed_files = set()
        for doc in processed_docs:
            if "/" in doc.file_path:
                object_name = doc.file_path.split("/")[-1]
                processed_files.add(object_name)

        # 미처리 파일들
        unprocessed_files = [f for f in pdf_files if f not in processed_files]

        db.close()

        return {
            "total_files_in_minio": len(pdf_files),
            "processed_files_count": len(processed_files),
            "unprocessed_files_count": len(unprocessed_files),
            "unprocessed_files": unprocessed_files,
            "file_watcher_running": file_watcher_service.running,
            "webhook_endpoint": "/api/v1/minio/webhook",
        }

    except Exception as e:
        print(f"자동 처리 테스트 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"테스트 중 오류 발생: {str(e)}"
        )


@router.get("/sync/status")
async def get_minio_db_sync_status():
    """
    MinIO-DB 동기화 상태 조회

    orphaned 문서가 있는지 확인합니다.
    """
    try:
        status = get_sync_status()
        return {
            "minio_files": status["minio_files"],
            "db_documents": status["db_documents"],
            "orphaned_documents": status["orphaned_documents"],
            "is_synced": status["is_synced"],
            "sync_status": "동기화됨" if status["is_synced"] else "동기화 필요",
        }

    except Exception as e:
        print(f"동기화 상태 조회 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"동기화 상태 조회 중 오류 발생: {str(e)}"
        )


@router.post("/sync/cleanup")
async def manual_cleanup_orphaned_data():
    """
    수동으로 orphaned 데이터 정리

    MinIO에 없는 파일들의 DB 데이터를 정리합니다.
    """
    try:
        success = cleanup_orphaned_data_on_startup()

        if success:
            # 정리 후 상태 재조회
            status = get_sync_status()
            return {
                "message": "Orphaned 데이터 정리 완료",
                "success": True,
                "current_status": {
                    "minio_files": status["minio_files"],
                    "db_documents": status["db_documents"],
                    "orphaned_documents": status["orphaned_documents"],
                    "is_synced": status["is_synced"],
                }
            }
        else:
            return {
                "message": "Orphaned 데이터 정리 실패",
                "success": False,
            }

    except Exception as e:
        print(f"수동 orphaned 데이터 정리 오류: {e}")
        raise HTTPException(
            status_code=500, detail=f"정리 중 오류 발생: {str(e)}"
        )
