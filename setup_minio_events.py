#!/usr/bin/env python3
"""
MinIO Event Notification 설정 스크립트
"""

import json
import time

import requests
from minio import Minio
from minio.commonconfig import ENABLED
from minio.notificationconfig import NotificationConfig, WebhookConfig


def setup_minio_events():
    """MinIO Event Notification 설정"""
    # MinIO 클라이언트 설정
    client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )

    bucket_name = "pdf-documents"
    webhook_url = "http://app:8000/api/v1/minio/webhook"

    try:
        print("MinIO Event Notification 설정 시작...")

        # 버킷이 존재하는지 확인
        if not client.bucket_exists(bucket_name):
            print(
                f"버킷 '{bucket_name}'이 존재하지 않습니다. 먼저 버킷을 생성하세요."
            )
            return False

        # 웹훅 설정 - 생성 및 삭제 이벤트 모두 처리
        webhook_config = WebhookConfig(
            "pdf_processor",  # 웹훅 ID
            webhook_url,  # 웹훅 URL
            ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],  # 이벤트 타입
            enabled=ENABLED,  # 활성화
        )

        # Notification 설정
        notification_config = NotificationConfig(
            webhook_config_list=[webhook_config]
        )

        # 버킷에 notification 설정 적용
        client.set_bucket_notification(bucket_name, notification_config)

        print(f"✅ 버킷 '{bucket_name}'에 Event Notification 설정 완료")
        print(f"   웹훅 URL: {webhook_url}")
        print("   이벤트: s3:ObjectCreated:*, s3:ObjectRemoved:*")

        # 설정 확인
        config = client.get_bucket_notification(bucket_name)
        print(
            f"✅ 설정 확인 완료: {len(config.webhook_config_list)}개 웹훅 설정됨"
        )

        return True

    except Exception as e:
        print(f"❌ MinIO Event Notification 설정 실패: {e}")
        return False


def test_webhook_endpoint():
    """웹훅 엔드포인트 테스트"""
    try:
        test_payload = {
            "Records": [
                {
                    "eventVersion": "2.0",
                    "eventSource": "minio:s3",
                    "eventName": "s3:ObjectCreated:Put",
                    "eventTime": "2024-01-01T00:00:00.000Z",
                    "s3": {
                        "bucket": {"name": "pdf-documents"},
                        "object": {"key": "test.pdf"},
                    },
                }
            ]
        }

        response = requests.post(
            "http://localhost:8000/api/v1/minio/webhook",
            json=test_payload,
            timeout=10,
        )

        if response.status_code == 200:
            print("✅ 웹훅 엔드포인트 테스트 성공")
            return True
        else:
            print(f"❌ 웹훅 엔드포인트 테스트 실패: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 웹훅 엔드포인트 테스트 오류: {e}")
        return False


def wait_for_services():
    """서비스들이 준비될 때까지 대기"""
    print("서비스 준비 상태 확인 중...")

    # MinIO 대기
    for i in range(30):
        try:
            response = requests.get(
                "http://localhost:9000/minio/health/live", timeout=5
            )
            if response.status_code == 200:
                print("✅ MinIO 준비 완료")
                break
        except Exception:
            if i == 29:
                print("❌ MinIO 연결 실패")
                return False
            time.sleep(2)

    # FastAPI 대기
    for i in range(30):
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ FastAPI 준비 완료")
                break
        except Exception:
            if i == 29:
                print("❌ FastAPI 연결 실패")
                return False
            time.sleep(2)

    return True


if __name__ == "__main__":
    print("=== MinIO Auto-Processing Setup ===")

    # 서비스 준비 대기
    if not wait_for_services():
        exit(1)

    # 웹훅 엔드포인트 테스트
    if not test_webhook_endpoint():
        print("⚠️  웹훅 엔드포인트에 문제가 있지만 계속 진행합니다.")

    # MinIO Event Notification 설정
    if setup_minio_events():
        print("\n🎉 자동 처리 시스템 설정 완료!")
        print("\n사용법:")
        print("1. MinIO에 PDF 파일을 업로드하면 자동으로 임베딩 처리됩니다")
        print("2. API 업로드: POST /api/v1/documents/upload")
        print("3. 상태 확인: GET /api/v1/file-watcher/status")
        print("4. 테스트: GET /api/v1/auto-processing/test")
    else:
        print("\n❌ 설정 실패")
        exit(1)
