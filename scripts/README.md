# Scripts 디렉토리

이 디렉토리는 AI Planner 백엔드 프로젝트의 유틸리티 스크립트들을 포함합니다.

## 스크립트 목록

### 1. cleanup_orphaned_data.py

MinIO와 데이터베이스 간의 동기화 문제를 해결하는 정리 도구입니다.

**용도:**

-   MinIO에 없는 파일들의 DB 데이터 정리
-   orphaned 문서 및 청크 삭제
-   벡터 스토어 데이터 정리

**사용법:**

```bash
# 프로젝트 루트에서 실행
python scripts/cleanup_orphaned_data.py
```

**옵션:**

1. 현재 상태만 확인
2. orphaned 데이터 정리

### 2. setup_minio_events.py

MinIO Event Notification을 설정하여 자동 PDF 처리 시스템을 구성합니다.

**용도:**

-   MinIO 웹훅 이벤트 설정
-   파일 업로드/삭제 시 자동 처리 활성화
-   웹훅 엔드포인트 테스트

**사용법:**

```bash
# Docker 환경이 실행된 상태에서
python scripts/setup_minio_events.py
```

**전제조건:**

-   MinIO 서버 실행 중 (localhost:9000)
-   FastAPI 애플리케이션 실행 중 (localhost:8000)
-   pdf-documents 버킷 생성됨

## 주의사항

1. **실행 위치**: 모든 스크립트는 프로젝트 루트 디렉토리에서 실행해야 합니다.
2. **환경 설정**: Docker 환경 또는 적절한 Python 환경이 설정되어 있어야 합니다.
3. **백업**: 데이터 정리 스크립트 실행 전에는 항상 데이터를 백업하세요.

## 환경변수

스크립트들은 다음 환경변수들을 사용할 수 있습니다:

-   DATABASE_URL
-   MINIO_ENDPOINT
-   MINIO_ACCESS_KEY
-   MINIO_SECRET_KEY

자세한 설정은 프로젝트 루트의 README.md를 참조하세요.
