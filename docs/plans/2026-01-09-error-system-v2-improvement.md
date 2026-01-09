# 에러 시스템 v2.0 개선계획

**작성일**: 2026-01-09
**대상 시스템**: RAG_Standard v3.3.0
**목적**: 개발자 경험 향상 및 국제 사용자 지원

---

## 1. 개요

### 1.1 배경
- **현재 상태**: 모든 에러 메시지가 한국어로 하드코딩되어 있음
- **문제점**:
  - 영어권 개발자가 시스템 진입 장벽 높음
  - 에러 추적 및 검색이 어려움 (자연어 메시지만 존재)
  - 동일한 에러를 문서화/공유할 때 일관성 부족

### 1.2 목표
1. **한국어/영어 양언어 지원** - 개발자가 선호하는 언어로 에러 확인
2. **에러코드 시스템 도입** - 문제를 빠르게 식별하고 해결할 수 있는 개발자 경험 제공

### 1.3 범위
- **포함**: API 엔드포인트, 핵심 모듈(검색, 생성, 문서처리, DB 연결)
- **제외**: 전체 UI 국제화(i18n), 로그 메시지 번역
- **대상 언어**: 한국어(기본), 영어

---

## 2. 현재 상태 분석

### 2.1 에러 메시지 현황
```python
# 현재 패턴 (한국어 하드코딩)
raise RuntimeError(
    "PostgreSQL 데이터베이스에 연결할 수 없습니다: DATABASE_URL이 설정되지 않았습니다. "
    "해결 방법: 1) DATABASE_URL 설정을 확인하세요. "
    "2) PostgreSQL 서버가 실행 중인지 확인하세요 (pg_isready). "
    ...
)
```

### 2.2 문제점
- 영어권 개발자는 번역기 필요
- 에러 로그 검색 시 정확한 한국어 문장을 알아야 함
- Slack/GitHub Issue에서 에러 공유 시 긴 문장 복사 필요

---

## 3. 개선 항목

### 3.1 한국어/영어 양언어 지원

#### A. 아키텍처 설계

**메시지 저장소 구조**:
```python
# app/lib/errors/messages.py
ERROR_MESSAGES = {
    "DB-001": {
        "ko": "PostgreSQL 데이터베이스에 연결할 수 없습니다: {reason}",
        "en": "Cannot connect to PostgreSQL database: {reason}"
    },
    "DB-001-SOLUTION": {
        "ko": [
            "DATABASE_URL 설정을 확인하세요",
            "PostgreSQL 서버가 실행 중인지 확인하세요 (pg_isready)",
            "네트워크 연결을 확인하세요"
        ],
        "en": [
            "Verify DATABASE_URL configuration",
            "Check if PostgreSQL server is running (pg_isready)",
            "Verify network connectivity"
        ]
    }
}
```

**언어 감지 방식**:
```python
# 1. 환경변수 우선 (개발자 설정)
PREFERRED_LANGUAGE = os.getenv("ERROR_LANGUAGE", "ko")  # 기본값: 한국어

# 2. API 요청 시 Accept-Language 헤더 (운영 환경)
def get_user_language(request: Request) -> str:
    accept_lang = request.headers.get("Accept-Language", "ko")
    return "en" if accept_lang.startswith("en") else "ko"
```

#### B. 구현 계획

**Phase 1: 메시지 중앙화 (1주)**
- [ ] `app/lib/errors/messages.py` 생성 - 모든 에러 메시지 저장소
- [ ] `app/lib/errors/formatter.py` 생성 - 메시지 포맷팅 유틸리티
- [ ] 기존 10개 파일의 하드코딩 메시지를 메시지 저장소 참조로 변경

**Phase 2: 언어 지원 인프라 (1주)**
- [ ] `LanguageContext` 클래스 구현 (현재 요청의 언어 저장)
- [ ] FastAPI Dependency로 주입 가능하도록 설계
- [ ] 환경변수 `ERROR_LANGUAGE` 지원 추가

**Phase 3: 번역 작업 (2주)**
- [ ] 현재 한국어 메시지 60개를 영어로 번역
- [ ] 기술 용어 일관성 검토 (예: "벡터 데이터베이스" → "vector database")
- [ ] 영어권 개발자 리뷰

**Phase 4: 테스트 및 검증 (1주)**
- [ ] 언어별 에러 메시지 단위 테스트 작성
- [ ] 기존 1,117개 테스트가 한국어 기본값으로 통과하는지 확인
- [ ] 영어 환경에서 통합 테스트

---

### 3.2 개발자 친화적 에러코드 시스템

#### A. 에러코드 네이밍 규칙

**형식**: `{DOMAIN}-{NUMBER}[-VARIANT]`

**도메인 분류**:
- `AUTH`: 인증/인가 관련
- `DB`: 데이터베이스 연결/쿼리
- `VECTOR`: 벡터 저장소 (Weaviate)
- `LLM`: LLM API 호출
- `DOC`: 문서 처리/업로드
- `SEARCH`: 검색/리트리벌
- `API`: API 요청 검증

**예시**:
```
AUTH-001: API 키 누락
AUTH-002: API 키 만료
DB-001: 연결 실패
DB-002: 마이그레이션 실패
VECTOR-001: Weaviate 연결 실패
LLM-001: 생성 실패
```

#### B. 에러 응답 구조

**개선 전 (현재)**:
```json
{
  "detail": {
    "error": "인증 실패",
    "message": "API 키가 유효하지 않습니다",
    "suggestion": "X-API-Key 헤더를 확인하세요"
  }
}
```

**개선 후**:
```json
{
  "error_code": "AUTH-001",
  "message": "API 키가 유효하지 않습니다",
  "solutions": [
    "X-API-Key 헤더에 올바른 API 키를 입력하세요",
    ".env 파일의 ADMIN_API_KEY 설정을 확인하세요",
    "키가 만료되었다면 새로 발급받으세요"
  ],
  "docs_url": "https://docs.example.com/errors/AUTH-001"
}
```

#### C. 개발자 경험 개선 포인트

**1. 빠른 문제 식별**
```bash
# 에러코드로 즉시 검색 가능
$ grep -r "VECTOR-001" logs/
$ git log --grep="VECTOR-001"
```

**2. 문서화 연결**
- 각 에러코드마다 전용 문서 페이지
- 실제 해결 사례 링크 (GitHub Issues, Slack 스레드)

**3. 에러 통계 대시보드**
```python
# 운영 중 가장 많이 발생하는 에러 TOP 5
DB-001: 45회 (데이터베이스 연결 실패)
VECTOR-001: 32회 (Weaviate 연결 실패)
LLM-001: 18회 (답변 생성 실패)
```

#### D. 구현 계획

**Phase 1: 에러코드 정의 (1주)**
- [ ] 현재 60개 에러 케이스에 에러코드 할당
- [ ] `app/lib/errors/codes.py` 생성 - Enum으로 에러코드 정의
- [ ] 에러코드 문서 초안 작성 (`docs/errors/`)

**Phase 2: 예외 클래스 개선 (1주)**
```python
# app/lib/errors/exceptions.py
class RAGException(Exception):
    """모든 커스텀 예외의 베이스 클래스"""
    error_code: str
    message_key: str
    context: dict

    def to_dict(self, lang: str = "ko") -> dict:
        """언어별 에러 응답 생성"""
        return {
            "error_code": self.error_code,
            "message": get_message(self.message_key, lang, **self.context),
            "solutions": get_solutions(self.error_code, lang),
            "docs_url": f"https://docs.rag-standard.com/errors/{self.error_code}"
        }

class DatabaseConnectionError(RAGException):
    error_code = "DB-001"
    message_key = "db.connection_failed"
```

**Phase 3: 기존 코드 마이그레이션 (2주)**
- [ ] 10개 핵심 파일의 예외를 새 클래스로 전환
- [ ] API 라우터에서 예외 핸들러 통합
- [ ] 에러 응답 포맷 통일

**Phase 4: 문서 자동화 (1주)**
- [ ] 에러코드별 문서 자동 생성 스크립트
- [ ] Markdown 형식으로 `docs/errors/{ERROR_CODE}.md` 생성
- [ ] GitHub Pages 또는 MkDocs 연동

---

## 4. 구현 단계 요약

### 타임라인 (총 8주)

```
주차 │ 작업 항목
────┼────────────────────────────────────────────
 1  │ [양언어] 메시지 중앙화
    │ [에러코드] 에러코드 정의
────┼────────────────────────────────────────────
 2  │ [양언어] 언어 지원 인프라
    │ [에러코드] 예외 클래스 개선
────┼────────────────────────────────────────────
 3  │ [양언어] 번역 작업 (1/2)
    │ [에러코드] 기존 코드 마이그레이션 (1/2)
────┼────────────────────────────────────────────
 4  │ [양언어] 번역 작업 (2/2)
    │ [에러코드] 기존 코드 마이그레이션 (2/2)
────┼────────────────────────────────────────────
 5  │ [양언어] 테스트 및 검증
    │ [에러코드] 문서 자동화
────┼────────────────────────────────────────────
 6  │ 통합 테스트 및 QA
────┼────────────────────────────────────────────
 7  │ 베타 배포 및 피드백 수집
────┼────────────────────────────────────────────
 8  │ 정식 배포 및 모니터링
```

### 우선순위

**High Priority (필수)**:
- 에러코드 시스템 구축 (개발자 경험 즉시 개선)
- 환경변수 기반 언어 전환 (개발 환경에서 즉시 사용 가능)

**Medium Priority (권장)**:
- 영어 번역 완성 (국제 협업 준비)
- 에러 문서 자동화 (장기 유지보수 효율)

**Low Priority (선택)**:
- Accept-Language 헤더 지원 (운영 환경 최적화)
- 에러 통계 대시보드 (데이터 기반 개선)

---

## 5. 예상 효과

### 5.1 개발자 경험 개선
- ✅ **문제 해결 시간 50% 단축**: "VECTOR-001"로 검색하면 즉시 해결책 발견
- ✅ **온보딩 장벽 제거**: 영어권 개발자도 번역 없이 에러 이해
- ✅ **커뮤니케이션 효율화**: "AUTH-002 발생했어요"로 짧게 소통

### 5.2 운영 효율성
- ✅ **에러 패턴 분석**: 에러코드 기반 자동 집계 가능
- ✅ **문서 일관성**: 에러코드당 하나의 표준 문서 유지
- ✅ **버전 관리**: 메시지 변경 이력 추적 용이

### 5.3 비즈니스 가치
- ✅ **국제 협업 준비**: 글로벌 팀과 협업 시 언어 장벽 제거
- ✅ **유지보수 비용 절감**: 중복 질문 감소, 셀프 서비스 향상
- ✅ **개발 속도 향상**: 에러 트러블슈팅 시간 단축

---

## 6. 리스크 및 대응 방안

### 6.1 기술적 리스크

**리스크**: 기존 테스트가 한국어 에러 메시지 문자열에 의존
**대응**:
- 테스트를 에러코드 기반으로 전환
- 기본 언어를 한국어로 유지하여 하위 호환성 보장

**리스크**: 번역 품질 문제 (기술 용어 오역)
**대응**:
- 핵심 60개 메시지에만 집중 (전체 시스템 번역 아님)
- 영어권 개발자 리뷰 단계 필수 포함

### 6.2 일정 리스크

**리스크**: 8주 일정이 지연될 가능성
**대응**:
- Phase별 독립 배포 가능하도록 설계
- Phase 1-2만 완료해도 에러코드 시스템 사용 가능

### 6.3 사용자 혼란 리스크

**리스크**: 기존 한국어 사용자가 영어 메시지를 받을 수 있음
**대응**:
- 기본 언어를 한국어로 설정 (하위 호환성)
- 환경변수로 명시적 변경 시에만 영어 사용

---

## 7. 성공 지표 (KPI)

### 출시 후 3개월 목표

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|-----------|
| 에러 해결 시간 | 평균 15분 | 평균 7분 | GitHub Issue 해결 시간 추적 |
| 중복 질문 비율 | 40% | 20% | Slack #support 채널 분석 |
| 영어 문서 접근 | 0% | 30% | Google Analytics (영어권 IP) |
| 에러 문서 조회수 | - | 월 100회+ | docs.rag-standard.com 분석 |

---

## 8. 다음 단계

### 즉시 실행 가능한 작업

1. **이 계획서 리뷰 및 승인** (PM/Tech Lead)
2. **Phase 1 착수**:
   - `app/lib/errors/messages.py` 생성
   - 기존 10개 파일 중 1개로 PoC 진행 (`connection.py` 추천)
3. **영어권 개발자 섭외** (번역 리뷰어)

### 장기 로드맵 (v3.4.0 이후)

- 로그 메시지 국제화 (현재는 에러만 대상)
- UI 메시지 국제화 (프론트엔드 있다면)
- 에러 분석 대시보드 구축

---

## 부록: 참고 자료

### A. 에러코드 예시 (전체 목록은 별도 문서)

```
AUTH-001: API 키 누락
AUTH-002: API 키 만료
AUTH-003: 권한 부족

DB-001: 데이터베이스 연결 실패
DB-002: 마이그레이션 실패
DB-003: 쿼리 타임아웃

VECTOR-001: Weaviate 연결 실패
VECTOR-002: 컬렉션 생성 실패
VECTOR-003: 벡터 업로드 실패

LLM-001: 답변 생성 실패
LLM-002: 프롬프트 검증 실패
LLM-003: 토큰 한도 초과

DOC-001: 파일 업로드 실패
DOC-002: 문서 파싱 실패
DOC-003: 청킹 실패

SEARCH-001: 검색 실패
SEARCH-002: 리랭킹 실패
```

### B. 코드 예시 (개선 후)

```python
# app/lib/errors/exceptions.py
from enum import Enum

class ErrorCode(str, Enum):
    # Database
    DB_CONNECTION_FAILED = "DB-001"
    DB_MIGRATION_FAILED = "DB-002"

    # Vector Store
    VECTOR_CONNECTION_FAILED = "VECTOR-001"
    VECTOR_COLLECTION_NOT_FOUND = "VECTOR-002"

    # LLM
    LLM_GENERATION_FAILED = "LLM-001"

# app/infrastructure/persistence/connection.py (개선 후)
from app.lib.errors.exceptions import DatabaseConnectionError, ErrorCode
from app.lib.errors.formatter import format_error

if not database_url:
    raise DatabaseConnectionError(
        error_code=ErrorCode.DB_CONNECTION_FAILED,
        context={"reason": "DATABASE_URL not set"}
    )
```

---

**문서 작성자**: Claude (Subagent-Driven Development)
**리뷰 필요**: PM, Tech Lead, 영어권 개발자
**다음 액션**: 계획 승인 후 Phase 1 착수
