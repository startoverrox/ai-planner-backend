"""
MinIO 기반 파일 저장 서비스
"""

import io
import os
from typing import BinaryIO, Optional
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()


class StorageService:
    def __init__(self):
        # MinIO 클라이언트 초기화
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = os.getenv("MINIO_BUCKET", "pdf-documents")

        # HTTPS 사용 여부 결정 (개발 환경에서는 HTTP 사용)
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        self.client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=secure,
        )

        # 버킷 생성 (존재하지 않는 경우)
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """버킷이 존재하지 않으면 생성"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"버킷 '{self.bucket_name}' 생성 완료")
        except S3Error as e:
            print(f"버킷 확인/생성 중 오류 발생: {e}")

    def upload_file(
        self,
        file_data: BinaryIO,
        object_name: str,
        content_type: str = "application/pdf",
    ) -> bool:
        """파일을 MinIO에 업로드"""
        try:
            # 파일 크기 계산
            file_data.seek(0, 2)  # 끝으로 이동
            file_size = file_data.tell()
            file_data.seek(0)  # 처음으로 이동

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type,
            )
            print(f"파일 '{object_name}' 업로드 완료")
            return True

        except S3Error as e:
            print(f"파일 업로드 중 오류 발생: {e}")
            return False

    def upload_file_from_path(
        self, file_path: str, object_name: Optional[str] = None
    ) -> bool:
        """로컬 파일을 MinIO에 업로드"""
        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type="application/pdf",
            )
            print(f"파일 '{file_path}' -> '{object_name}' 업로드 완료")
            return True

        except S3Error as e:
            print(f"파일 업로드 중 오류 발생: {e}")
            return False

    def download_file(self, object_name: str) -> Optional[io.BytesIO]:
        """MinIO에서 파일 다운로드 (메모리로)"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            file_data = io.BytesIO(response.read())
            response.close()
            response.release_conn()
            return file_data

        except S3Error as e:
            print(f"파일 다운로드 중 오류 발생: {e}")
            return None

    def download_file_to_path(self, object_name: str, file_path: str) -> bool:
        """MinIO에서 파일 다운로드 (로컬 파일로)"""
        try:
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
            )
            print(f"파일 '{object_name}' -> '{file_path}' 다운로드 완료")
            return True

        except S3Error as e:
            print(f"파일 다운로드 중 오류 발생: {e}")
            return False

    def get_file_url(
        self, object_name: str, expires_seconds: int = 3600
    ) -> Optional[str]:
        """파일의 임시 접근 URL 생성"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires_seconds,
            )
            return url

        except S3Error as e:
            print(f"URL 생성 중 오류 발생: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """파일 삭제"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            print(f"파일 '{object_name}' 삭제 완료")
            return True

        except S3Error as e:
            print(f"파일 삭제 중 오류 발생: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """파일 존재 여부 확인"""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False

    def list_files(self, prefix: str = "") -> list:
        """파일 목록 조회"""
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name, prefix=prefix, recursive=True
            )
            return [obj.object_name for obj in objects]

        except S3Error as e:
            print(f"파일 목록 조회 중 오류 발생: {e}")
            return []


# 전역 스토리지 서비스 인스턴스
storage_service = StorageService()
