# AI Planner Backend

RAG(Retrieval-Augmented Generation) 기반 문서 질의응답 시스템

## 🚀 주요 기능

-   **PDF 문서 처리**: PDF 파일을 청크 단위로 분할하여 처리
-   **MinIO Object Storage**: S3 호환 파일 저장 및 관리
-   **자동 임베딩**: 파일 업로드 시 실시간 자동 임베딩 처리
-   **자동 DB 동기화**: 파일 삭제 시 데이터베이스에서도 자동으로 관련 데이터 정리
-   **벡터 검색**: PostgreSQL + pgvector를 이용한 의미 기반 문서 검색
-   **AI 답변 생성**: Ollama를 통한 자연어 답변 생성
-   **REST API**: FastAPI 기반 RESTful API 제공

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  PostgreSQL +   │    │     Ollama      │
│  (Auto Embed)   │◄──►│    pgvector     │    │ (host installed)│
│    (Docker)     │    │    (Docker)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   MinIO Storage │    │  Vector Store   │
│ (S3 Compatible) │    │(embedding store)│
│    (Docker)     │    │                 │
└─────────────────┘    └─────────────────┘
         ▲
         │ Event Notification
         ▼
┌─────────────────┐
│  File Watcher   │
│  (Auto Process) │
└─────────────────┘
```

## 📋 사전 요구사항

1. **Docker & Docker Compose**
2. **Ollama 설치** (호스트 시스템에)

    ```bash
    # Ollama 설치 (Linux/macOS)
    curl -fsSL https://ollama.ai/install.sh | sh

    # 모델 다운로드
    ollama pull llama3.2:3b
    ```

## 🛠️ 설치 및 실행

### 1. 환경 설정

**`.env` 파일 내용:**

```env
# 데이터베이스 설정
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/ai_planner

# MinIO 설정 (Object Storage)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET=pdf-documents
MINIO_SECURE=false

# AWS 호환 설정 (MinIO 서명 오류 해결)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123

# Ollama 설정 (호스트에 설치된 Ollama)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:3b

# FastAPI 설정
API_V1_STR=/api/v1
PROJECT_NAME=AI Planner Backend
DEBUG=True

# 임베딩 모델 설정
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# 청킹 설정
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 2. Docker로 실행

```bash
# 데이터베이스만 먼저 실행
docker-compose up postgres -d

# 전체 시스템 실행
docker-compose up --build -d
```

### 3. 개발 환경 실행

```bash
# 가상환경 생성 및 활성화docke
py -3.13 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 마이그레이션
alembic upgrade head

# 애플리케이션 실행 (방법 1 - 권장)
fastapi dev app/main.py

# 애플리케이션 실행 (방법 2)
uvicorn app.main:app --reload
```

## 📚 API 사용법

### 문서 처리

```bash
# PDF 파일 업로드 및 자동 임베딩 (추천)
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@sample.pdf"

# MinIO Storage에 있는 파일 처리
curl -X POST "http://localhost:8000/api/v1/documents/process-from-storage" \
  -H "Content-Type: application/json" \
  -d '{"object_name": "sample.pdf"}'

# 문서 목록 조회
curl "http://localhost:8000/api/v1/documents"

# 문서 상세 조회
curl "http://localhost:8000/api/v1/documents/{document_id}"
```

### Storage 관리

```bash
# MinIO Storage 파일 목록 조회
curl "http://localhost:8000/api/v1/storage/files"

# 파일 다운로드 URL 생성
curl "http://localhost:8000/api/v1/storage/files/{object_name}/url"
```

### 자동 처리 시스템

**파일 업로드 시 자동 임베딩:**
MinIO에 PDF 파일이 업로드되면 자동으로 임베딩 처리됩니다.

**파일 삭제 시 자동 DB 정리:**
MinIO에서 PDF 파일이 삭제되면 데이터베이스의 관련 데이터도 자동으로 정리됩니다.

-   `documents` 테이블에서 해당 문서 레코드 삭제
-   `document_chunks` 테이블에서 해당 문서의 모든 청크 삭제
-   벡터 스토어에서 해당 문서의 임베딩 데이터 삭제

```bash
# File Watcher 상태 확인
curl "http://localhost:8000/api/v1/file-watcher/status"

# File Watcher 강제 실행
curl -X POST "http://localhost:8000/api/v1/file-watcher/force-check"

# 자동 처리 시스템 테스트
curl "http://localhost:8000/api/v1/auto-processing/test"
```

### 질의응답

```bash
# 질문하기
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "문서의 주요 내용은 무엇인가요?",
    "k": 5
  }'
```

### API 문서 및 관리 도구

-   **Swagger UI**: http://localhost:8000/docs
-   **ReDoc**: http://localhost:8000/redoc
-   **MinIO Console**: http://localhost:9001 (ID: minioadmin, PW: minioadmin123)

## 📁 프로젝트 구조

```
ai-planner-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 메인 애플리케이션
│   ├── api/                 # API 라우터
│   │   └── v1/
│   │       ├── chat.py      # 채팅 API
│   │       └── documents.py # 문서 관리 API
│   ├── core/                # 설정 및 보안
│   │   └── config.py        # 환경 설정
│   ├── models/              # 데이터베이스 모델
│   │   └── documents.py     # 문서 모델
│   ├── services/            # 비즈니스 로직
│   │   ├── embedding.py     # 임베딩 서비스
│   │   ├── pdf_processor.py # PDF 처리 서비스
│   │   ├── vector_store.py  # 벡터 스토어 서비스
│   │   ├── storage.py       # MinIO 스토리지 서비스
│   │   ├── file_watcher.py  # 파일 감시 서비스
│   │   └── rag.py           # RAG 서비스
│   ├── db/                  # 데이터베이스 관련
│   │   └── database.py      # 데이터베이스 연결
│   └── utils/               # 유틸리티
├── alembic/                 # 데이터베이스 마이그레이션
├── test/                    # 테스트 코드
├── setup_minio_events.py    # MinIO 이벤트 설정 스크립트
├── docker-compose.yml       # Docker 설정
├── Dockerfile              # 애플리케이션 Docker 이미지
├── requirements.txt        # Python 의존성
└── README.md               # 이 파일
```

## 🔧 설정 옵션

### MinIO 설정

-   `MINIO_ROOT_USER`: MinIO 관리자 사용자명 (기본: minioadmin)
-   `MINIO_ROOT_PASSWORD`: MinIO 관리자 비밀번호 (기본: minioadmin123)

### 청킹 설정

-   `CHUNK_SIZE`: 텍스트 청크 크기 (기본: 1000)
-   `CHUNK_OVERLAP`: 청크 간 겹치는 부분 (기본: 200)

### 검색 설정

-   API 호출 시 `k` 파라미터로 검색할 문서 수 조절

### Ollama 모델 변경

```bash
# 다른 모델 사용
ollama pull llama3.1:8b
# .env 파일에서 OLLAMA_MODEL 값 변경
```

### 자동 처리 설정

**MinIO 이벤트 알림 설정:**
파일 업로드 및 삭제 이벤트를 자동으로 처리하도록 설정합니다.

```bash
# MinIO Event Notification 설정 (업로드 + 삭제 이벤트)
python setup_minio_events.py

# File Watcher 간격 조정 (app/services/file_watcher.py)
check_interval = 30  # 30초 간격
```

**처리되는 이벤트:**

-   `s3:ObjectCreated:*`: 파일 업로드 시 자동 임베딩 처리
-   `s3:ObjectRemoved:*`: 파일 삭제 시 자동 DB 정리

## 🐛 문제 해결

### MinIO 연결 오류

```bash
# MinIO 컨테이너 상태 확인
docker-compose logs minio

# MinIO Event Notification 설정
python setup_minio_events.py

# MinIO 재시작
docker-compose restart minio
```

### MinIO SignatureDoesNotMatch 오류

MinIO 직접 접속은 되지만 애플리케이션에서 서명 오류가 발생하는 경우:

**1. 환경변수 추가 설정:**

```env
# .env 파일에 추가
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
```

**2. 터미널에서 환경변수 설정 (임시):**

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin123
```

**3. MinIO 서버 재시작:**

```bash
docker-compose restart minio
```

**4. 애플리케이션 재시작:**

```bash
# 개발 모드 재시작 (방법 1 - 권장)
fastapi dev app/main.py

# 개발 모드 재시작 (방법 2)
uvicorn app.main:app --reload

# 또는 Docker 재시작
docker-compose restart app
```

### SSL 연결 오류

```bash
# MINIO_SECURE 환경변수 확인
echo $MINIO_SECURE  # false여야 함

# docker-compose.yml에서 MINIO_SECURE=false 설정 확인
```

### 자동 임베딩 동작 안함

```bash
# File Watcher 상태 확인
curl "http://localhost:8000/api/v1/file-watcher/status"

# 자동 처리 시스템 테스트
curl "http://localhost:8000/api/v1/auto-processing/test"

# 수동으로 파일 처리
curl -X POST "http://localhost:8000/api/v1/file-watcher/force-check"
```

### Ollama 연결 오류

```bash
# Ollama 서비스 상태 확인
ollama list

# Ollama 서비스 재시작
systemctl restart ollama  # Linux
```

### 데이터베이스 연결 오류

```bash
# PostgreSQL 컨테이너 로그 확인
docker-compose logs postgres

# 데이터베이스 재시작
docker-compose restart postgres
```

### 벡터 확장 오류

```sql
-- PostgreSQL에 수동으로 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;
```
