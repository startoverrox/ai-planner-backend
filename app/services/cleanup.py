"""
MinIO-DB 동기화 및 orphaned 데이터 정리 서비스
"""

from typing import List

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.documents import Document, DocumentChunk
from app.services.storage import storage_service
from app.services.vector_store import vector_store_service


def get_minio_pdf_files() -> set:
    """MinIO에서 PDF 파일 목록 조회"""
    try:
        minio_files = storage_service.list_files()
        return set(f for f in minio_files if f.endswith('.pdf'))
    except Exception as e:
        print(f"MinIO 파일 목록 조회 오류: {e}")
        return set()


def find_orphaned_documents(db: Session, minio_pdf_files: set) -> List[Document]:
    """orphaned 문서 찾기"""
    db_documents = db.query(Document).all()
    orphaned_docs = []

    for doc in db_documents:
        # file_path에서 파일명 추출
        if doc.file_path.startswith('minio://'):
            file_name = doc.file_path.split('/')[-1]
        else:
            file_name = doc.filename

        # MinIO에 파일이 없으면 orphaned
        if file_name not in minio_pdf_files:
            orphaned_docs.append(doc)

    return orphaned_docs


def delete_orphaned_document(db: Session, doc: Document) -> bool:
    """단일 orphaned 문서 삭제"""
    try:
        document_id = str(doc.id)

        # 벡터 스토어에서 삭제
        try:
            vector_store_service.delete_document(document_id)
        except Exception as e:
            print(f"벡터 스토어 삭제 오류 ({doc.filename}): {e}")

        # DB에서 청크 삭제
        chunks_deleted = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete()

        # 문서 삭제
        db.delete(doc)

        print(f"✅ orphaned 문서 삭제 완료: {doc.filename} (청크 {chunks_deleted}개)")
        return True

    except Exception as e:
        print(f"❌ orphaned 문서 삭제 실패 ({doc.filename}): {e}")
        return False


def cleanup_orphaned_data_on_startup() -> bool:
    """
    앱 시작 시 orphaned 데이터 자동 정리

    Returns:
        bool: 정리 성공 여부
    """
    try:
        print("🧹 Orphaned 데이터 정리 시작...")

        db = SessionLocal()

        # 1. MinIO 파일 목록 조회
        minio_pdf_files = get_minio_pdf_files()

        # 2. orphaned 문서 찾기
        orphaned_docs = find_orphaned_documents(db, minio_pdf_files)

        if not orphaned_docs:
            print("✅ 정리할 orphaned 데이터가 없습니다.")
            db.close()
            return True

        print(f"🗑️  {len(orphaned_docs)}개의 orphaned 문서 발견")
        print(f"   MinIO 파일: {len(minio_pdf_files)}개")
        print(f"   정리 대상: {len(orphaned_docs)}개")

        # 3. orphaned 문서들 삭제
        cleaned_count = 0
        for doc in orphaned_docs:
            if delete_orphaned_document(db, doc):
                cleaned_count += 1

        # 4. 변경사항 커밋
        db.commit()
        db.close()

        print("🎉 Orphaned 데이터 정리 완료!")
        print(f"   정리된 문서: {cleaned_count}개")
        print(f"   실패한 문서: {len(orphaned_docs) - cleaned_count}개")

        return True

    except Exception as e:
        print(f"❌ Orphaned 데이터 정리 오류: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False


def get_sync_status() -> dict:
    """
    MinIO-DB 동기화 상태 조회

    Returns:
        dict: 동기화 상태 정보
    """
    try:
        db = SessionLocal()

        # MinIO 파일 조회
        minio_pdf_files = get_minio_pdf_files()

        # DB 문서 조회
        db_documents = db.query(Document).all()

        # orphaned 문서 찾기
        orphaned_docs = find_orphaned_documents(db, minio_pdf_files)

        db.close()

        return {
            "minio_files": len(minio_pdf_files),
            "db_documents": len(db_documents),
            "orphaned_documents": len(orphaned_docs),
            "is_synced": len(orphaned_docs) == 0,
        }

    except Exception as e:
        print(f"동기화 상태 조회 오류: {e}")
        return {
            "minio_files": 0,
            "db_documents": 0,
            "orphaned_documents": 0,
            "is_synced": False,
            "error": str(e),
        }
