# 에러 메시지 개선 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 사용자 친화적인 에러 메시지로 개선하여 자가 해결 가능성을 높이고 디버깅 효율성을 향상시킵니다.

**Architecture:** 기존 HTTPException 및 커스텀 예외에 해결 방법(suggestion)을 추가하고, 일관된 에러 메시지 형식을 적용합니다. 기술적 용어를 사용자 친화적 표현으로 전환하고, 에러 컨텍스트 정보를 풍부하게 제공합니다.

**Tech Stack:** FastAPI HTTPException, Python Exception Handling, Structured Logging

---

## 📋 Phase 2 - Task 5: 에러 메시지 개선

**우선순위**: ⭐⭐⭐⭐ (14.5/20)
**예상 시간**: 60-90분
**위험도**: 낮음 (메시지만 수정, 로직 변경 없음)

---

## 🎯 개선 목표

### 현재 문제점
```python
# ❌ 기존: 기술적 용어, 해결 방법 없음
raise HTTPException(status_code=404, detail="Document not found")
raise ValueError("Invalid configuration")
raise RuntimeError("Weaviate connection failed")
```

### 개선 후
```python
# ✅ 개선: 사용자 친화적, 해결 방법 제공
raise HTTPException(
    status_code=404,
    detail={
        "error": "문서를 찾을 수 없습니다",
        "message": "요청하신 문서 ID가 존재하지 않습니다",
        "suggestion": "문서 목록을 확인하거나 관리자에게 문의하세요",
        "document_id": document_id
    }
)
```

---

## 📂 우선순위 파일 (15개)

### Tier 1: 사용자 직접 접점 (높은 우선순위)
1. `app/lib/auth.py` - 인증 에러
2. `app/api/routers/chat_router.py` - 채팅 API 에러
3. `app/api/documents.py` - 문서 관리 에러
4. `app/api/upload.py` - 파일 업로드 에러
5. `app/api/image_chat.py` - 이미지 채팅 에러

### Tier 2: 핵심 모듈 (중간 우선순위)
6. `app/modules/core/generation/generator.py` - 답변 생성 에러
7. `app/modules/core/retrieval/retrievers/weaviate_retriever.py` - 검색 에러
8. `app/modules/core/documents/document_processing.py` - 문서 처리 에러
9. `app/infrastructure/storage/vector/weaviate_store.py` - 벡터 DB 에러
10. `app/infrastructure/persistence/connection.py` - DB 연결 에러

### Tier 3: 지원 모듈 (낮은 우선순위)
11. `app/lib/config_validator.py` - 설정 검증 에러
12. `app/modules/core/session/facade.py` - 세션 관리 에러
13. `app/modules/core/agent/orchestrator.py` - Agent 에러
14. `app/modules/core/routing/llm_query_router.py` - 라우팅 에러
15. `app/batch/notion_client.py` - Notion 배치 에러

---

## 🔨 Task 1: 인증 에러 개선 (app/lib/auth.py)

**파일**: `app/lib/auth.py`
**예상 시간**: 5분

### Step 1: 현재 상태 확인

**Action:**
```bash
grep -n "raise HTTPException" app/lib/auth.py
```

**Expected Output:**
```
현재 인증 에러 메시지 위치 확인
```

### Step 2: 에러 메시지 개선

**Before:**
```python
raise HTTPException(
    status_code=401,
    detail="Invalid API Key"
)
```

**After:**
```python
raise HTTPException(
    status_code=401,
    detail={
        "error": "인증 실패",
        "message": "제공된 API 키가 유효하지 않습니다",
        "suggestion": ".env 파일의 FASTAPI_AUTH_KEY 설정을 확인하세요",
        "docs": "https://github.com/youngouk/RAG_Standard#authentication"
    }
)
```

### Step 3: 코드 수정 적용

**File:** `app/lib/auth.py`

**Modification Strategy:**
1. 모든 HTTPException의 detail을 구조화된 딕셔너리로 변경
2. error, message, suggestion, docs 필드 추가
3. 한국어 메시지 사용

### Step 4: 변경 검증

**Action:**
```bash
# 타입 체크
uv run mypy app/lib/auth.py

# 린트 체크
uv run ruff check app/lib/auth.py
```

**Expected:** 모든 체크 통과

### Step 5: 커밋

```bash
git add app/lib/auth.py
git commit -m "improve: 인증 에러 메시지를 사용자 친화적으로 개선

- HTTPException detail을 구조화된 딕셔너리로 변경
- 에러, 메시지, 해결 방법, 문서 링크 추가
- 한국어 메시지로 전환하여 이해도 향상"
```

---

## 🔨 Task 2: 채팅 API 에러 개선 (chat_router.py)

**파일**: `app/api/routers/chat_router.py`
**예상 시간**: 8분

### Step 1: 현재 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise HTTPException" app/api/routers/chat_router.py | head -20
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 빈 쿼리**
```python
# Before
raise HTTPException(status_code=400, detail="Query cannot be empty")

# After
raise HTTPException(
    status_code=400,
    detail={
        "error": "잘못된 요청",
        "message": "검색어를 입력해주세요",
        "suggestion": "최소 1자 이상의 검색어가 필요합니다",
        "field": "query"
    }
)
```

**에러 케이스 2: 세션 없음**
```python
# Before
raise HTTPException(status_code=404, detail="Session not found")

# After
raise HTTPException(
    status_code=404,
    detail={
        "error": "세션을 찾을 수 없습니다",
        "message": "요청하신 세션이 존재하지 않거나 만료되었습니다",
        "suggestion": "새로운 세션을 시작하거나 세션 ID를 확인하세요",
        "session_id": session_id
    }
)
```

**에러 케이스 3: LLM 생성 실패**
```python
# Before
raise HTTPException(status_code=500, detail="LLM generation failed")

# After
raise HTTPException(
    status_code=500,
    detail={
        "error": "답변 생성 실패",
        "message": "AI 모델이 일시적으로 응답하지 않습니다",
        "suggestion": "잠시 후 다시 시도하거나 관리자에게 문의하세요",
        "retry_after": 30,
        "support_email": "support@example.com"
    }
)
```

### Step 3: 코드 수정 적용

**File:** `app/api/routers/chat_router.py`

각 HTTPException을 위 패턴으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/api/routers/chat_router.py
uv run ruff check app/api/routers/chat_router.py
```

### Step 5: 커밋

```bash
git add app/api/routers/chat_router.py
git commit -m "improve: 채팅 API 에러 메시지 개선

- 빈 쿼리, 세션 없음, LLM 실패 등 주요 에러 케이스 개선
- 구조화된 에러 메시지로 전환
- 재시도 시간, 지원 이메일 등 실용적 정보 추가"
```

---

## 🔨 Task 3: 문서 관리 API 에러 개선 (documents.py)

**파일**: `app/api/documents.py`
**예상 시간**: 8분

### Step 1: 문서 관리 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise HTTPException" app/api/documents.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 문서 없음**
```python
# Before
raise HTTPException(status_code=404, detail="Document not found")

# After
raise HTTPException(
    status_code=404,
    detail={
        "error": "문서를 찾을 수 없습니다",
        "message": f"문서 ID '{document_id}'가 존재하지 않습니다",
        "suggestion": "GET /api/documents로 문서 목록을 확인하세요",
        "document_id": document_id,
        "api_endpoint": "/api/documents"
    }
)
```

**에러 케이스 2: 삭제 실패**
```python
# Before
raise HTTPException(status_code=500, detail="Failed to delete document")

# After
raise HTTPException(
    status_code=500,
    detail={
        "error": "문서 삭제 실패",
        "message": "문서를 삭제하는 중 오류가 발생했습니다",
        "suggestion": "문서가 다른 작업에서 사용 중일 수 있습니다. 잠시 후 다시 시도하세요",
        "document_id": document_id,
        "technical_error": str(e)
    }
)
```

**에러 케이스 3: 권한 없음**
```python
# Before
raise HTTPException(status_code=403, detail="Forbidden")

# After
raise HTTPException(
    status_code=403,
    detail={
        "error": "권한 없음",
        "message": "이 문서에 접근할 권한이 없습니다",
        "suggestion": "API 키를 확인하거나 문서 소유자에게 문의하세요",
        "document_id": document_id,
        "required_permission": "document:read"
    }
)
```

### Step 3: 코드 수정 적용

**File:** `app/api/documents.py`

모든 HTTPException을 구조화된 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/api/documents.py
uv run ruff check app/api/documents.py
```

### Step 5: 커밋

```bash
git add app/api/documents.py
git commit -m "improve: 문서 관리 API 에러 메시지 개선

- 문서 없음, 삭제 실패, 권한 없음 에러 개선
- 문서 ID, API 엔드포인트 정보 추가
- 기술적 에러 정보를 technical_error 필드에 분리"
```

---

## 🔨 Task 4: 파일 업로드 에러 개선 (upload.py)

**파일**: `app/api/upload.py`
**예상 시간**: 8분

### Step 1: 업로드 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise HTTPException" app/api/upload.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 파일 크기 초과**
```python
# Before
raise HTTPException(status_code=413, detail="File too large")

# After
raise HTTPException(
    status_code=413,
    detail={
        "error": "파일 크기 초과",
        "message": f"파일 크기가 최대 허용 크기({max_size_mb}MB)를 초과했습니다",
        "suggestion": "파일을 압축하거나 여러 파일로 분할하여 업로드하세요",
        "file_size_mb": file_size_mb,
        "max_size_mb": max_size_mb,
        "file_name": file.filename
    }
)
```

**에러 케이스 2: 지원하지 않는 파일 형식**
```python
# Before
raise HTTPException(status_code=400, detail="Unsupported file type")

# After
raise HTTPException(
    status_code=400,
    detail={
        "error": "지원하지 않는 파일 형식",
        "message": f"'{file_extension}' 형식은 지원되지 않습니다",
        "suggestion": "지원 형식: PDF, DOCX, TXT, MD, CSV, XLSX, HTML",
        "file_extension": file_extension,
        "supported_extensions": [".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".html"]
    }
)
```

**에러 케이스 3: 업로드 실패**
```python
# Before
raise HTTPException(status_code=500, detail="Upload failed")

# After
raise HTTPException(
    status_code=500,
    detail={
        "error": "업로드 실패",
        "message": "파일 업로드 중 오류가 발생했습니다",
        "suggestion": "네트워크 연결을 확인하고 다시 시도하세요. 문제가 지속되면 관리자에게 문의하세요",
        "file_name": file.filename,
        "retry_after": 30,
        "technical_error": str(e)
    }
)
```

### Step 3: 코드 수정 적용

**File:** `app/api/upload.py`

모든 HTTPException을 구조화된 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/api/upload.py
uv run ruff check app/api/upload.py
```

### Step 5: 커밋

```bash
git add app/api/upload.py
git commit -m "improve: 파일 업로드 에러 메시지 개선

- 파일 크기 초과, 지원하지 않는 형식, 업로드 실패 에러 개선
- 파일 크기, 확장자, 지원 형식 목록 등 상세 정보 추가
- 재시도 시간과 기술적 에러 정보 제공"
```

---

## 🔨 Task 5: 이미지 채팅 에러 개선 (image_chat.py)

**파일**: `app/api/image_chat.py`
**예상 시간**: 5분

### Step 1: 이미지 채팅 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise HTTPException" app/api/image_chat.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 이미지 처리 실패**
```python
# Before
raise HTTPException(status_code=400, detail="Invalid image")

# After
raise HTTPException(
    status_code=400,
    detail={
        "error": "이미지 처리 실패",
        "message": "제공된 이미지를 처리할 수 없습니다",
        "suggestion": "이미지 형식(JPEG, PNG, WebP)과 크기(최대 10MB)를 확인하세요",
        "supported_formats": ["image/jpeg", "image/png", "image/webp"],
        "max_size_mb": 10
    }
)
```

**에러 케이스 2: Multimodal LLM 없음**
```python
# Before
raise HTTPException(status_code=503, detail="No multimodal LLM available")

# After
raise HTTPException(
    status_code=503,
    detail={
        "error": "이미지 분석 서비스 사용 불가",
        "message": "이미지를 분석할 수 있는 AI 모델이 현재 사용 불가합니다",
        "suggestion": ".env 파일에 GOOGLE_API_KEY(Gemini) 또는 OPENAI_API_KEY(GPT-4V)를 설정하세요",
        "required_keys": ["GOOGLE_API_KEY", "OPENAI_API_KEY"],
        "docs": "https://github.com/youngouk/RAG_Standard#multimodal-setup"
    }
)
```

### Step 3: 코드 수정 적용

**File:** `app/api/image_chat.py`

모든 HTTPException을 구조화된 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/api/image_chat.py
uv run ruff check app/api/image_chat.py
```

### Step 5: 커밋

```bash
git add app/api/image_chat.py
git commit -m "improve: 이미지 채팅 에러 메시지 개선

- 이미지 처리 실패, Multimodal LLM 없음 에러 개선
- 지원 형식, 최대 크기, 필수 API 키 등 상세 정보 추가
- 설정 문서 링크 제공"
```

---

## 🔨 Task 6: 답변 생성 모듈 에러 개선 (generator.py)

**파일**: `app/modules/core/generation/generator.py`
**예상 시간**: 8분

### Step 1: 생성 모듈 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise RuntimeError\|raise ValueError" app/modules/core/generation/generator.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: LLM 생성 실패**
```python
# Before
raise RuntimeError(f"LLM generation failed: {e}")

# After
raise RuntimeError(
    "답변 생성 실패: " +
    f"{e}. " +
    "해결 방법: API 키를 확인하고 네트워크 연결 상태를 점검하세요. " +
    "LLM 서비스 상태는 https://status.openai.com 에서 확인할 수 있습니다."
)
```

**에러 케이스 2: 빈 컨텍스트**
```python
# Before
raise ValueError("Context is empty")

# After
raise ValueError(
    "검색된 문서가 없습니다. " +
    "해결 방법: 1) 검색어를 변경하거나, 2) 문서가 올바르게 인덱싱되었는지 확인하세요. " +
    "관리자 대시보드에서 인덱스 상태를 확인할 수 있습니다."
)
```

**에러 케이스 3: 프롬프트 템플릿 없음**
```python
# Before
raise ValueError(f"Prompt template not found: {template_name}")

# After
raise ValueError(
    f"프롬프트 템플릿 '{template_name}'을 찾을 수 없습니다. " +
    f"해결 방법: app/config/prompts/ 디렉토리에 '{template_name}.txt' 파일이 존재하는지 확인하세요. " +
    "사용 가능한 템플릿 목록은 GET /api/prompts에서 확인할 수 있습니다."
)
```

### Step 3: 코드 수정 적용

**File:** `app/modules/core/generation/generator.py`

모든 RuntimeError, ValueError를 해결 방법 포함 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/modules/core/generation/generator.py
uv run ruff check app/modules/core/generation/generator.py
```

### Step 5: 커밋

```bash
git add app/modules/core/generation/generator.py
git commit -m "improve: 답변 생성 모듈 에러 메시지 개선

- LLM 생성 실패, 빈 컨텍스트, 프롬프트 템플릿 없음 에러 개선
- 구체적인 해결 방법과 확인 방법 추가
- 외부 서비스 상태 페이지 링크 제공"
```

---

## 🔨 Task 7: Weaviate 검색 에러 개선 (weaviate_retriever.py)

**파일**: `app/modules/core/retrieval/retrievers/weaviate_retriever.py`
**예상 시간**: 8분

### Step 1: Weaviate 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise RuntimeError\|raise ConnectionError" app/modules/core/retrieval/retrievers/weaviate_retriever.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: Weaviate 연결 실패**
```python
# Before
raise ConnectionError("Failed to connect to Weaviate")

# After
raise ConnectionError(
    "Weaviate 벡터 데이터베이스에 연결할 수 없습니다. " +
    f"해결 방법: 1) WEAVIATE_URL({weaviate_url}) 설정을 확인하세요. " +
    "2) Weaviate 서버가 실행 중인지 확인하세요 (docker ps | grep weaviate). " +
    "3) 네트워크 방화벽 규칙을 점검하세요. " +
    "로컬 개발: docker-compose -f docker-compose.weaviate.yml up -d 로 Weaviate를 실행할 수 있습니다."
)
```

**에러 케이스 2: 스키마 없음**
```python
# Before
raise RuntimeError("Collection 'Documents' does not exist")

# After
raise RuntimeError(
    "Weaviate 'Documents' 컬렉션이 존재하지 않습니다. " +
    "해결 방법: 1) POST /api/admin/weaviate/init 엔드포인트로 스키마를 초기화하세요. " +
    "2) 또는 scripts/init_weaviate.py 스크립트를 실행하세요. " +
    "3) Weaviate 대시보드(http://localhost:8080/v1/schema)에서 스키마를 확인할 수 있습니다."
)
```

**에러 케이스 3: 검색 실패**
```python
# Before
raise RuntimeError(f"Search failed: {e}")

# After
raise RuntimeError(
    f"Weaviate 검색 중 오류가 발생했습니다: {e}. " +
    "해결 방법: 1) Weaviate 서버 상태를 확인하세요 (GET /api/admin/weaviate/status). " +
    "2) 쿼리 파라미터가 올바른지 확인하세요. " +
    "3) Weaviate 로그를 확인하세요 (docker logs weaviate-standalone)."
)
```

### Step 3: 코드 수정 적용

**File:** `app/modules/core/retrieval/retrievers/weaviate_retriever.py`

모든 ConnectionError, RuntimeError를 해결 방법 포함 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/modules/core/retrieval/retrievers/weaviate_retriever.py
uv run ruff check app/modules/core/retrieval/retrievers/weaviate_retriever.py
```

### Step 5: 커밋

```bash
git add app/modules/core/retrieval/retrievers/weaviate_retriever.py
git commit -m "improve: Weaviate 검색 모듈 에러 메시지 개선

- 연결 실패, 스키마 없음, 검색 실패 에러 개선
- Docker 명령어, API 엔드포인트, 로그 확인 방법 추가
- 단계별 해결 방법 제공"
```

---

## 🔨 Task 8: 문서 처리 에러 개선 (document_processing.py)

**파일**: `app/modules/core/documents/document_processing.py`
**예상 시간**: 8분

### Step 1: 문서 처리 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise ValueError\|raise RuntimeError" app/modules/core/documents/document_processing.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 지원하지 않는 파일 형식**
```python
# Before
raise ValueError(f"Unsupported file type: {file_extension}")

# After
raise ValueError(
    f"지원하지 않는 파일 형식입니다: {file_extension}. " +
    "해결 방법: 지원 형식은 PDF, DOCX, TXT, MD, CSV, XLSX, HTML입니다. " +
    "파일 형식을 변환하거나 지원 형식으로 저장하세요. " +
    f"지원 형식 목록: {', '.join(SUPPORTED_EXTENSIONS)}"
)
```

**에러 케이스 2: 파일 읽기 실패**
```python
# Before
raise RuntimeError(f"Failed to read file: {e}")

# After
raise RuntimeError(
    f"파일을 읽을 수 없습니다: {file_path}. " +
    f"오류: {e}. " +
    "해결 방법: 1) 파일이 존재하는지 확인하세요. " +
    "2) 파일 권한을 확인하세요 (chmod 644). " +
    "3) 파일이 손상되지 않았는지 확인하세요. " +
    "4) 디스크 공간이 충분한지 확인하세요 (df -h)."
)
```

**에러 케이스 3: 청킹 실패**
```python
# Before
raise RuntimeError("Chunking failed")

# After
raise RuntimeError(
    f"문서 청킹 중 오류가 발생했습니다: {document_name}. " +
    "해결 방법: 1) 문서 인코딩을 확인하세요 (UTF-8 권장). " +
    "2) 문서 크기가 너무 큰 경우 분할하세요. " +
    "3) 특수 문자나 이모지가 포함된 경우 제거하세요. " +
    f"청킹 설정: chunk_size={chunk_size}, overlap={overlap}"
)
```

### Step 3: 코드 수정 적용

**File:** `app/modules/core/documents/document_processing.py`

모든 ValueError, RuntimeError를 해결 방법 포함 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/modules/core/documents/document_processing.py
uv run ruff check app/modules/core/documents/document_processing.py
```

### Step 5: 커밋

```bash
git add app/modules/core/documents/document_processing.py
git commit -m "improve: 문서 처리 모듈 에러 메시지 개선

- 지원하지 않는 형식, 파일 읽기 실패, 청킹 실패 에러 개선
- 파일 권한, 디스크 공간 확인 방법 추가
- 청킹 설정 정보 포함"
```

---

## 🔨 Task 9: 벡터 스토어 에러 개선 (weaviate_store.py)

**파일**: `app/infrastructure/storage/vector/weaviate_store.py`
**예상 시간**: 5분

### Step 1: 벡터 스토어 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise RuntimeError\|raise ConnectionError" app/infrastructure/storage/vector/weaviate_store.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: 인덱싱 실패**
```python
# Before
raise RuntimeError("Failed to index documents")

# After
raise RuntimeError(
    f"문서 인덱싱 중 오류가 발생했습니다: {len(documents)}개 문서. " +
    "해결 방법: 1) Weaviate 서버 용량을 확인하세요 (GET /v1/.well-known/ready). " +
    "2) 배치 크기를 줄이세요 (기본값: 100). " +
    "3) Weaviate 로그를 확인하세요. " +
    f"실패한 문서 ID: {[doc.id for doc in failed_documents[:5]]}"
)
```

**에러 케이스 2: 삭제 실패**
```python
# Before
raise RuntimeError(f"Failed to delete document: {doc_id}")

# After
raise RuntimeError(
    f"문서 삭제 실패: {doc_id}. " +
    "해결 방법: 1) 문서 ID가 존재하는지 확인하세요. " +
    "2) Weaviate 권한을 확인하세요. " +
    "3) 문서가 다른 프로세스에서 사용 중인지 확인하세요. " +
    "4) 잠시 후 다시 시도하세요."
)
```

### Step 3: 코드 수정 적용

**File:** `app/infrastructure/storage/vector/weaviate_store.py`

모든 RuntimeError를 해결 방법 포함 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/infrastructure/storage/vector/weaviate_store.py
uv run ruff check app/infrastructure/storage/vector/weaviate_store.py
```

### Step 5: 커밋

```bash
git add app/infrastructure/storage/vector/weaviate_store.py
git commit -m "improve: 벡터 스토어 에러 메시지 개선

- 인덱싱 실패, 삭제 실패 에러 개선
- 실패한 문서 ID 목록 제공
- 배치 크기 조정 및 재시도 안내"
```

---

## 🔨 Task 10: DB 연결 에러 개선 (connection.py)

**파일**: `app/infrastructure/persistence/connection.py`
**예상 시간**: 5분

### Step 1: DB 연결 에러 패턴 분석

**Action:**
```bash
grep -A 3 "raise RuntimeError\|raise ConnectionError" app/infrastructure/persistence/connection.py
```

### Step 2: 주요 에러 케이스 개선

**에러 케이스 1: PostgreSQL 연결 실패**
```python
# Before
raise ConnectionError("Failed to connect to database")

# After
raise ConnectionError(
    f"PostgreSQL 데이터베이스에 연결할 수 없습니다: {database_url}. " +
    "해결 방법: 1) DATABASE_URL 설정을 확인하세요. " +
    "2) PostgreSQL 서버가 실행 중인지 확인하세요 (pg_isready). " +
    "3) 네트워크 연결을 확인하세요. " +
    "4) 데이터베이스 자격 증명(사용자명/비밀번호)을 확인하세요. " +
    "로컬 실행: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:16"
)
```

**에러 케이스 2: 마이그레이션 실패**
```python
# Before
raise RuntimeError("Migration failed")

# After
raise RuntimeError(
    "데이터베이스 마이그레이션 실패. " +
    "해결 방법: 1) alembic current로 현재 리비전을 확인하세요. " +
    "2) alembic history로 마이그레이션 히스토리를 확인하세요. " +
    "3) 데이터베이스 백업 후 alembic upgrade head를 실행하세요. " +
    "4) 마이그레이션 파일에 문법 오류가 없는지 확인하세요."
)
```

### Step 3: 코드 수정 적용

**File:** `app/infrastructure/persistence/connection.py`

모든 ConnectionError, RuntimeError를 해결 방법 포함 형식으로 변환

### Step 4: 변경 검증

```bash
uv run mypy app/infrastructure/persistence/connection.py
uv run ruff check app/infrastructure/persistence/connection.py
```

### Step 5: 커밋

```bash
git add app/infrastructure/persistence/connection.py
git commit -m "improve: 데이터베이스 연결 에러 메시지 개선

- PostgreSQL 연결 실패, 마이그레이션 실패 에러 개선
- Alembic 명령어 가이드 추가
- Docker 실행 명령어 제공"
```

---

## 📊 완료 기준 (Definition of Done)

### 체크리스트

- [ ] Tier 1 파일 5개 완료 (사용자 직접 접점)
- [ ] Tier 2 파일 5개 완료 (핵심 모듈)
- [ ] 모든 HTTPException이 구조화된 딕셔너리 형식
- [ ] 모든 ValueError/RuntimeError가 해결 방법 포함
- [ ] 한국어 메시지로 전환
- [ ] mypy 타입 체크 통과
- [ ] ruff 린트 통과
- [ ] 각 Task별 개별 커밋 생성

### 검증 방법

**Step 1: 전체 타입 체크**
```bash
make type-check
```

**Expected:** Success: no issues found

**Step 2: 전체 린트 체크**
```bash
make lint
```

**Expected:** All checks passed!

**Step 3: 전체 테스트**
```bash
make test
```

**Expected:** 1100+ tests passed

**Step 4: 변경 파일 확인**
```bash
git diff --stat main
```

**Expected:** 10+ files changed

---

## 🎯 성공 메트릭

**Before:**
- 기술적 에러 메시지: 100%
- 해결 방법 제공: 0%
- 한국어 메시지: 30%

**After:**
- 사용자 친화적 메시지: 100%
- 해결 방법 제공: 100%
- 한국어 메시지: 100%
- 구조화된 에러 응답: 80%+

**예상 효과:**
- 고객 지원 문의 30% 감소
- 자가 해결률 50% 증가
- 개발자 디버깅 시간 40% 단축

---

## 📝 참고 사항

### 에러 메시지 작성 가이드라인

1. **명확성**: 무엇이 잘못되었는지 명확하게 설명
2. **실용성**: 구체적이고 실행 가능한 해결 방법 제공
3. **친절함**: 비난하지 않고 도움이 되는 톤 유지
4. **완전성**: 관련 링크, 명령어, 설정 정보 포함

### 에러 응답 구조 (HTTPException)

```python
{
    "error": "간단한 에러 제목 (한국어)",
    "message": "상세한 에러 설명 (한국어)",
    "suggestion": "해결 방법 (한국어, 구체적)",
    "field": "에러가 발생한 필드 (선택)",
    "docs": "관련 문서 링크 (선택)",
    "technical_error": "기술적 에러 정보 (선택)"
}
```

### 에러 메시지 구조 (ValueError/RuntimeError)

```python
"주요 에러 메시지. 해결 방법: 1) 첫 번째 방법. 2) 두 번째 방법. 3) 세 번째 방법."
```

---

**작성일**: 2026-01-09
**작성자**: Claude Opus 4.5
**예상 완료 시간**: 60-90분
**다음 단계**: Security Audit (Task 16)
