# 에러 처리 라이브러리 (v3.3.0)

RAG 시스템의 에러 코드, 메시지, 예외 클래스를 제공하는 통합 에러 처리 라이브러리입니다.

## 주요 기능

- **81개 에러 코드**: 도메인별로 분류된 표준 에러 코드
- **양언어 지원**: 한국어(기본) 및 영어 메시지 제공
- **해결 방법 제공**: 각 에러마다 구체적인 해결 방법 제공
- **타입 안전성**: 모든 함수에 명확한 타입 힌트

## 구조

```
app/lib/errors/
├── __init__.py         # 모듈 초기화 (주요 클래스/함수 export)
├── codes.py            # 에러 코드 Enum 정의 (81개)
├── messages.py         # 양언어 메시지 및 해결 방법 저장소
├── formatter.py        # 메시지 포맷팅 유틸리티
├── exceptions.py       # 커스텀 예외 클래스
└── README.md           # 이 문서
```

## 도메인별 에러 코드

| 도메인 | 개수 | 설명 |
|--------|------|------|
| AUTH | 6개 | 인증/인가 관련 |
| SESSION | 12개 | 세션 관리 |
| SERVICE | 2개 | 서비스 초기화 |
| DOC | 16개 | 문서 처리 |
| UPLOAD | 15개 | 파일 업로드 |
| IMAGE | 5개 | 이미지 처리 |
| LLM | 7개 | 언어 모델 |
| VECTOR | 12개 | 벡터 검색 |
| DB | 6개 | 데이터베이스 |

**총 81개 에러 코드**

## 사용 예시

### 1. 기본 사용법

```python
from app.lib.errors import ErrorCode, AuthError, get_error_message

# 예외 발생
raise AuthError(ErrorCode.AUTH_001)

# 에러 메시지 가져오기 (한국어 기본)
message = get_error_message("AUTH-001")
print(message)  # "FASTAPI_AUTH_KEY 환경 변수가 설정되지 않았습니다"

# 영어 메시지
message_en = get_error_message("AUTH-001", lang="en")
print(message_en)  # "FASTAPI_AUTH_KEY environment variable is not set"
```

### 2. 메시지 포맷팅

```python
from app.lib.errors import get_error_message

# 플레이스홀더가 있는 메시지 포맷팅
message = get_error_message("DB-002", lang="ko", reason="연결 타임아웃")
print(message)
# "PostgreSQL 데이터베이스에 연결할 수 없습니다: 연결 타임아웃"

message = get_error_message("UPLOAD-002", size=15, max_size=10)
print(message)
# "파일 크기 초과: 15MB (최대 10MB)"
```

### 3. 해결 방법 가져오기

```python
from app.lib.errors import get_error_solutions

solutions = get_error_solutions("AUTH-001", lang="ko")
for i, solution in enumerate(solutions, 1):
    print(f"{i}. {solution}")
# 1. 프로덕션 환경에서 FASTAPI_AUTH_KEY 환경 변수를 설정하세요
# 2. .env 파일에 FASTAPI_AUTH_KEY 값을 추가하세요
# 3. 환경 변수 설정 후 애플리케이션을 재시작하세요
```

### 4. 에러 응답 생성

```python
from app.lib.errors import format_error_response

response = format_error_response("AUTH-001", lang="en")
print(response)
# {
#     "error_code": "AUTH-001",
#     "message": "FASTAPI_AUTH_KEY environment variable is not set",
#     "solutions": [
#         "Set FASTAPI_AUTH_KEY environment variable in production",
#         "Add FASTAPI_AUTH_KEY value to .env file",
#         "Restart the application after setting environment variable"
#     ]
# }
```

### 5. 예외 클래스 사용

```python
from app.lib.errors import ErrorCode, DatabaseError

try:
    # 데이터베이스 연결 시도
    if not database_url:
        raise DatabaseError(ErrorCode.DB_001)
except DatabaseError as e:
    # 한국어 에러 응답
    response_ko = e.to_dict(lang="ko")
    print(response_ko["message"])

    # 영어 에러 응답
    response_en = e.to_dict(lang="en")
    print(response_en["message"])
    print(response_en["solutions"])
```

### 6. FastAPI 통합

```python
from fastapi import HTTPException
from app.lib.errors import ErrorCode, AuthError

@router.post("/api/admin/documents")
async def upload_document(api_key: str = Header(None)):
    if not api_key:
        error = AuthError(ErrorCode.AUTH_003)
        raise HTTPException(
            status_code=401,
            detail=error.to_dict(lang="en")
        )
    # ... 문서 업로드 로직
```

### 7. 환경변수로 기본 언어 변경

```bash
# .env 파일
ERROR_LANGUAGE=en  # 기본 언어를 영어로 변경
```

```python
from app.lib.errors import get_error_message

# ERROR_LANGUAGE=en인 경우, lang 파라미터 생략 시 영어 메시지 반환
message = get_error_message("AUTH-001")
print(message)  # "FASTAPI_AUTH_KEY environment variable is not set"
```

### 8. 모든 에러 코드 조회

```python
from app.lib.errors import get_all_error_codes, get_error_codes_by_domain

# 모든 에러 코드 조회
all_codes = get_all_error_codes()
print(f"총 {len(all_codes)}개 에러 코드")  # 총 81개 에러 코드

# 특정 도메인의 에러 코드 조회
auth_codes = get_error_codes_by_domain("AUTH")
print(auth_codes)
# ['AUTH-001', 'AUTH-002', 'AUTH-003', 'AUTH-004', 'AUTH-005', 'AUTH-006']
```

## 도메인별 예외 클래스

각 도메인마다 전용 예외 클래스를 제공합니다:

```python
from app.lib.errors import (
    AuthError,        # 인증/인가
    SessionError,     # 세션 관리
    ServiceError,     # 서비스 초기화
    DocumentError,    # 문서 처리
    UploadError,      # 파일 업로드
    ImageError,       # 이미지 처리
    LLMError,         # 언어 모델
    VectorError,      # 벡터 검색
    DatabaseError,    # 데이터베이스
)

# 사용 예시
raise AuthError(ErrorCode.AUTH_001)
raise DatabaseError(ErrorCode.DB_002, reason="연결 타임아웃")
raise UploadError(ErrorCode.UPLOAD_002, size=15, max_size=10)
```

## 기존 시스템과의 호환성

기존 에러 시스템(`app.lib.errors_legacy`)과 완전 호환됩니다:

```python
from app.lib.errors import (
    # 새 에러 시스템 (v3.3.0+)
    ErrorCode, AuthError, DatabaseError,

    # 기존 에러 시스템 (하위 호환성)
    ConfigError, RetrievalError, GenerationError
)

# 기존 코드는 그대로 작동
raise ConfigError("설정 파일을 찾을 수 없습니다")
raise RetrievalError("검색 실패")
```

## 타입 안전성

모든 함수는 명확한 타입 힌트를 제공하며, mypy strict 모드를 통과합니다:

```python
def get_error_message(
    error_code: str,
    lang: str | None = None,
    **kwargs: Any
) -> str: ...

def format_error_response(
    error_code: str,
    lang: str | None = None,
    include_solutions: bool = True,
    **context: Any,
) -> dict[str, Any]: ...
```

## 마이그레이션 가이드

기존 코드를 새 에러 시스템으로 점진적으로 마이그레이션하는 방법:

### Before (기존 방식)

```python
raise RuntimeError("PostgreSQL 데이터베이스에 연결할 수 없습니다: DATABASE_URL이 설정되지 않았습니다")
```

### After (새 에러 시스템)

```python
from app.lib.errors import ErrorCode, DatabaseError

raise DatabaseError(ErrorCode.DB_001)
```

### FastAPI 응답 개선

```python
# Before
@router.get("/documents")
async def get_documents():
    try:
        # ...
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# After
@router.get("/documents")
async def get_documents():
    try:
        # ...
    except Exception as e:
        error = DocumentError(ErrorCode.DOC_002, reason=str(e))
        raise HTTPException(
            status_code=500,
            detail=error.to_dict(lang="en")
        )
```

## 개발자 경험 개선 효과

1. **빠른 문제 식별**: 에러 코드로 즉시 검색 가능
   ```bash
   grep -r "DB-001" logs/
   git log --grep="DB-001"
   ```

2. **일관된 에러 응답**: 모든 API가 동일한 포맷 사용
   ```json
   {
     "error_code": "AUTH-001",
     "message": "...",
     "solutions": ["...", "..."]
   }
   ```

3. **국제 협업 준비**: 영어권 개발자도 번역 없이 에러 이해 가능

4. **자동 문서화**: 에러 코드와 메시지가 중앙화되어 문서 생성 용이

## 참고 자료

- 에러 코드 전체 목록: `/docs/plans/error-code-mapping.md`
- 개선 계획: `/docs/plans/2026-01-09-error-system-v2-improvement.md`
