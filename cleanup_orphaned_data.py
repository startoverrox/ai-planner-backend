#!/usr/bin/env python3
"""
MinIO에 없는 파일들의 DB 데이터 정리 스크립트
"""

import os
import sys

from sqlalchemy.orm import Session

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.documents import Document, DocumentChunk
from app.services.storage import storage_service
from app.services.vector_store import vector_store_service


def get_minio_files():
    """MinIO에서 PDF 파일 목록 조회"""
    print("\n1. MinIO 파일 목록 조회 중...")
    try:
        minio_files = storage_service.list_files()
        minio_pdf_files = set(f for f in minio_files if f.endswith('.pdf'))
        print(f"   MinIO에 있는 PDF 파일: {len(minio_pdf_files)}개")
        if minio_pdf_files:
            for file in minio_pdf_files:
                print(f"   - {file}")
        else:
            print("   - MinIO에 PDF 파일이 없습니다.")
        return minio_pdf_files
    except Exception as e:
        print(f"   ❌ MinIO 연결 오류: {e}")
        return None


def get_db_documents(db: Session):
    """DB에서 문서 목록 조회"""
    print("\n2. DB 문서 목록 조회 중...")
    db_documents = db.query(Document).all()
    print(f"   DB에 있는 문서: {len(db_documents)}개")
    return db_documents


def find_orphaned_documents(db_documents, minio_pdf_files):
    """orphaned 문서 찾기"""
    print("\n3. 정리 대상 문서 찾기...")
    orphaned_docs = []

    for doc in db_documents:
        # file_path에서 파일명 추출
        if doc.file_path.startswith('minio://'):
            # minio://bucket_name/filename.pdf -> filename.pdf
            file_name = doc.file_path.split('/')[-1]
        else:
            file_name = doc.filename

        # MinIO에 파일이 없으면 orphaned
        if file_name not in minio_pdf_files:
            orphaned_docs.append(doc)
            print(f"   🗑️  정리 대상: {doc.filename} (ID: {doc.id})")

    return orphaned_docs


def confirm_cleanup(orphaned_docs):
    """사용자에게 정리 확인"""
    print(f"\n⚠️  {len(orphaned_docs)}개의 orphaned 문서를 정리하시겠습니까?")
    print("   이 작업은 되돌릴 수 없습니다.")
    confirm = input("   계속하시겠습니까? (y/N): ").lower()
    return confirm == 'y'


def delete_single_document(db: Session, doc):
    """단일 문서 삭제 처리"""
    document_id = str(doc.id)
    print(f"   정리 중: {doc.filename} (ID: {document_id})")

    # 벡터 스토어에서 삭제
    try:
        vector_store_service.delete_document(document_id)
        print("     ✅ 벡터 스토어에서 삭제 완료")
    except Exception as e:
        print(f"     ⚠️  벡터 스토어 삭제 오류: {e}")

    # DB에서 청크 삭제
    chunks_deleted = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).delete()
    print(f"     ✅ 청크 {chunks_deleted}개 삭제 완료")

    # 문서 삭제
    db.delete(doc)
    print("     ✅ 문서 레코드 삭제 완료")


def execute_cleanup(db: Session, orphaned_docs):
    """정리 실행"""
    print(f"\n4. {len(orphaned_docs)}개 문서 정리 시작...")
    cleaned_count = 0

    for doc in orphaned_docs:
        try:
            delete_single_document(db, doc)
            cleaned_count += 1
        except Exception as e:
            print(f"     ❌ 문서 정리 오류 ({doc.filename}): {e}")
            continue

    return cleaned_count


def cleanup_orphaned_data():
    """MinIO에 없는 파일들의 DB 데이터 정리"""
    try:
        db = SessionLocal()
        print("=== MinIO-DB 동기화 정리 시작 ===")

        # 1. MinIO 파일 목록 조회
        minio_pdf_files = get_minio_files()
        if minio_pdf_files is None:
            return False

        # 2. DB 문서 목록 조회
        db_documents = get_db_documents(db)
        if not db_documents:
            print("   - DB에 문서가 없습니다.")
            db.close()
            return True

        # 3. orphaned 문서 찾기
        orphaned_docs = find_orphaned_documents(db_documents, minio_pdf_files)
        if not orphaned_docs:
            print("   ✅ 정리할 문서가 없습니다. DB와 MinIO가 동기화되어 있습니다.")
            db.close()
            return True

        # 4. 요약 출력
        print("\n📊 정리 요약:")
        print(f"   - MinIO 파일: {len(minio_pdf_files)}개")
        print(f"   - DB 문서: {len(db_documents)}개")
        print(f"   - 정리 대상: {len(orphaned_docs)}개")

        # 5. 사용자 확인
        if not confirm_cleanup(orphaned_docs):
            print("   정리 작업이 취소되었습니다.")
            db.close()
            return False

        # 6. 정리 실행
        cleaned_count = execute_cleanup(db, orphaned_docs)

        # 7. 커밋 및 결과 출력
        db.commit()
        db.close()

        print("\n🎉 정리 완료!")
        print(f"   - 정리된 문서: {cleaned_count}개")
        print(f"   - 실패한 문서: {len(orphaned_docs) - cleaned_count}개")

        return True

    except Exception as e:
        print(f"❌ 정리 스크립트 오류: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False


def show_current_status():
    """현재 상태만 보여주기"""
    try:
        db = SessionLocal()

        print("=== 현재 MinIO-DB 상태 ===")

        # MinIO 파일 목록
        try:
            minio_files = storage_service.list_files()
            minio_pdf_files = [f for f in minio_files if f.endswith('.pdf')]
            print(f"\n📁 MinIO 파일: {len(minio_pdf_files)}개")
            for file in minio_pdf_files:
                print(f"   - {file}")
        except Exception as e:
            print(f"❌ MinIO 연결 오류: {e}")

        # DB 문서 목록
        db_documents = db.query(Document).all()
        print(f"\n🗄️  DB 문서: {len(db_documents)}개")
        for doc in db_documents:
            chunks_count = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).count()
            print(f"   - {doc.filename} (청크: {chunks_count}개)")

        db.close()

    except Exception as e:
        print(f"❌ 상태 조회 오류: {e}")


if __name__ == "__main__":
    print("=== MinIO-DB 동기화 정리 도구 ===")
    print("\n옵션:")
    print("1. 현재 상태만 확인")
    print("2. orphaned 데이터 정리")

    choice = input("\n선택하세요 (1/2): ").strip()

    if choice == "1":
        show_current_status()
    elif choice == "2":
        cleanup_orphaned_data()
    else:
        print("잘못된 선택입니다.")
