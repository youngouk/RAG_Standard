# Changelog

프로젝트 변경 이력을 기록합니다. [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/) 형식을 따릅니다.

---

## [v3.3.1] - 2026-01-08

### Security
- **[CRITICAL]** SEC-001: 프로덕션 환경 인증 우회 취약점 수정 (CVSS 9.1)
  - 다층 환경 감지 로직 구현 (`app/lib/environment.py`)
  - 단일 환경 변수 조작으로 인증 우회 불가능
  - 프로덕션 지표: ENVIRONMENT, NODE_ENV, WEAVIATE_URL, FASTAPI_AUTH_KEY
  - `app/lib/auth.py` 인증 미들웨어 보안 강화
  - `main.py` 시작 시 프로덕션 환경 필수 변수 검증 추가
  - 14개 보안 테스트 추가 (환경 감지 9개, 인증 3개, Startup 2개)
  - 전체 테스트: 1110개 통과 (신규 14개 + 기존 1096개)

- **SEC-002**: 환경 변수 검증 부재 수정
  - 타입 안전성을 제공하는 환경 변수 로더 구현 (`app/lib/config_validator.py`)
  - `get_env_int()`: 정수 검증 (범위 검증 포함, 1-65535)
  - `get_env_bool()`: 불리언 검증 (True/False 값 정규화)
  - `get_env_url()`: URL 검증 (스킴, HTTPS 필수 옵션)
  - 런타임 환경 변수 타입 오류 사전 방지
  - `ConfigValidationError` 커스텀 예외로 명확한 에러 메시지 제공
  - 8개 검증 테스트 추가
  - 전체 테스트: 1104개 통과 (신규 8개 + 기존 1096개)

### Fixed
- **QA-001**: Documents 모듈 인코딩 처리 구현
  - chardet 기반 자동 인코딩 감지 (100KB 샘플링)
  - `detect_file_encoding()`: 파일 인코딩 자동 감지 (UTF-8/EUC-KR/CP949)
  - `safe_open_file()`: 인코딩 자동 감지 + 안전한 파일 열기
  - `stream_csv_chunks()`: 메모리 효율적 CSV 스트리밍 (pandas chunksize)
  - `stream_excel_sheets()`: Excel 시트별 스트리밍 (openpyxl)
  - CSV/XLSX 파일 처리 시 운영 환경 데이터 손실 위험 제거
  - 7개 테스트 추가 (인코딩 감지 4개, CSV 스트리밍 3개)
  - 전체 테스트: 1113개 통과 (신규 7개 + 기존 1106개)

- **QA-002**: Privacy 감사 로그 PII 노출 수정
  - MongoDB 감사 로그에 원본 PII 값 대신 SHA-256 해시 저장 (GDPR 준수)
  - `PIIAuditLogger._hash_value()`: SHA-256 해시 처리 (64자 hex)
  - `PIIAuditLogger._sanitize_metadata()`: 메타데이터 PII 패턴 제거 (전화번호 마스킹)
  - `AuditRecord.entities` 필드 추가: 해시 처리된 엔티티 저장
  - `log_detection()` 수정: 원본 값 대신 해시값 및 정제된 메타데이터 저장
  - 2개 PII 보호 테스트 추가 (`tests/modules/core/privacy/test_audit_pii_protection.py`)
  - 전체 테스트: 1106개 통과 (신규 2개 + 기존 1104개)

- **QA-003**: Agent 모듈 타임아웃 구현
  - AgentExecutor 전체 작업 타임아웃 구현 (무한 대기 방지)
  - `AgentConfig.timeout_seconds`: 전체 작업 타임아웃 (기본: 300초 = 5분)
  - `AgentExecutor.execute()`: `asyncio.wait_for()`로 타임아웃 적용
  - 환경변수 `AGENT_TIMEOUT_SECONDS`로 동적 설정 가능 (10초-1시간)
  - `app/lib/config_validator.get_env_int()` 활용: 타입 안전 환경변수 로딩
  - 타임아웃 초과 시 `asyncio.TimeoutError` 발생 및 로그 기록
  - 4개 타임아웃 테스트 추가 (`tests/modules/core/agent/test_agent_timeout.py`)
  - 전체 테스트: 1117개 통과 (신규 4개 + 기존 1113개)

### Improved
- **Quick Wins Phase 1**: 코드 품질 개선 적용
  - networkx_store.py 순환 import 제거 (logger 오류 수정)
  - 전체 테스트: 1117개 통과 (모든 기존 테스트 유지)

- **Quick Wins Phase 2**: 타입 안전성 및 코드 품질 강화
  - **Phase 2-1**: Python 3.10+ 타입 힌트 현대화
    - `Optional[T]` → `T | None` 변환 (PEP 604)
    - `from __future__ import annotations` 추가 (PEP 563)
    - Forward reference 따옴표 제거 (ruff UP037)
    - 수정 파일: `weaviate_client.py`, `mongodb_client.py`

  - **Phase 2-2**: RAG Pipeline 코드 정예화
    - `execute()` 함수 복잡도 감소 (20 → 11)
      - 5개 헬퍼 메서드 분리 (fallback, parallel_search, debug_track, metrics, trace)
    - `format_sources()` 함수 복잡도 감소 (19 → 제거)
      - 4개 헬퍼 메서드 분리 (rag_source, sql_row, multi_query, single_query)
    - 전체 복잡도: 37개 → 36개 함수 (복잡도 >10)

  - **Phase 2-3**: 설정 관리 개선
    - 환경별 설정 분리 (`app/config/environments/`)
      - development.yaml, test.yaml, production.yaml
    - Pydantic 검증 강화 (+235줄)
      - EnvironmentConfig, ServerConfig, LLMProviderSettings, CacheConfig, CircuitBreakerConfig
    - ConfigLoader 개선 (+64줄)
      - 환경 자동 감지 (4가지 지표 종합 판단)
      - base.yaml + environments/{env}.yaml 자동 병합
    - 문서화: `docs/config_management_improvements.md` (353줄)

- **Quick Wins Phase 2 추가**: 에러 및 로그 관리 개선
  - **표준 가이드라인 정의**
    - `docs/standards/logging_standards.md`: 로그 메시지 표준 (레벨별 용도, 형식, 보안)
    - `docs/standards/error_message_standards.md`: 에러 메시지 표준 (구조, 카테고리, 예시)

  - **환경 변수 문서화 강화**
    - `.env.example`: 102줄 → 308줄 (3배 증가)
    - 23개 환경 변수 완전 문서화 (목적/필수여부/기본값/예시/유효범위)
    - 주요 변수: FASTAPI_AUTH_KEY, GOOGLE_API_KEY, WEAVIATE_URL, MONGODB_URI, ENVIRONMENT

  - **에러 메시지 개선 (Phase 3)**
    - Tier 1 인프라 연결 파일 5개 개선
      - weaviate_client.py, mongodb_client.py, config_loader.py, environment.py, auth.py
    - 15개 에러 메시지에 3-5단계 해결 방법 추가
    - 모든 에러에 `suggestion` 필드 추가 (구체적 명령어/경로/환경변수 예시)
    - 프로덕션/개발 환경 구분하여 적절한 가이드 제공

  - **검증 결과**
    - 테스트: 1,117개 통과
    - 타입 체크: 350 파일 통과
    - 린트: 모든 검사 통과

---

## [3.1.0] - 2026-01-05

### Added
- **GraphRAG 모듈 구현** (`app/modules/core/graph/`)
  - `GraphRAGFactory`: 설정 기반 GraphRAG 컴포넌트 생성
  - `KnowledgeGraphBuilder`: LLM 기반 엔티티/관계 추출
  - `NetworkXGraphRepository`: NetworkX 기반 그래프 저장소
  - `Neo4jGraphStore`: Neo4j 프로덕션 그래프 저장소
  - 벡터+그래프 하이브리드 검색 (RRF 기반)
  - 89개 테스트 (GraphRAG) + 15개 테스트 (MCP 통합)
- **Agentic RAG 시스템** (`app/modules/core/agent/`)
  - `AgentOrchestrator`: ReAct 패턴 에이전트 루프
  - `AgentPlanner`: LLM 기반 도구 선택 (Function Calling)
  - `AgentExecutor`: 도구 병렬/순차 실행
  - `AgentSynthesizer`: 결과 합성 및 답변 생성
  - 81개 테스트, 96.69% 커버리지
- **시맨틱 캐시 활성화** (`cache.yaml` → `provider: "semantic"`)
  - 쿼리 임베딩 유사도 기반 캐시 히트
  - 20개 테스트, 93.94% 커버리지
- **ColBERT 리랭커 활성화** (`reranking.yaml` → `provider: "jina-colbert"`)
  - 토큰 수준 Late Interaction 리랭킹
  - 12개 테스트, 100% 커버리지

### Changed
- **Clean Architecture 강화** (Phase 1-3 리팩토링)
  - R1: `GPT5NanoReranker` → `OpenAILLMReranker` 전환
  - R2: deprecated 설정/코드 제거, TODO 해결
  - R3: 순환 의존성 제거, 인터페이스 일관성 검증
  - 아키텍처 테스트 25개 추가 (`tests/unit/architecture/`)
- **DI Container 리팩토링** - Provider 그룹 문서화, GraphRAG 컴포넌트 등록
- **테스트 범용화** - 특정 도메인 특화 테스트 데이터를 범용 데이터로 교체

### Added (Open Source)
- `.env.example`: 환경변수 예시 파일 추가

---

## [3.0.0] - 2026-01-02

### Added
- **Factory 패턴 확장**
  - `EmbedderFactory`: 설정 기반 임베더 생성 (Gemini, Qwen3, OpenAI)
  - `RerankerFactory`: 설정 기반 리랭커 생성 (Gemini Flash, Jina, ColBERT)
  - `CacheFactory`: 설정 기반 캐시 생성 (Memory, Redis, Semantic)
  - `MCPToolFactory`: MCP 도구 시스템 팩토리
- **MCP 도구 시스템** (`app/modules/core/mcp/`)
  - `search_vector_db`: 벡터 DB 하이브리드 검색
  - `get_document_by_id`: UUID 기반 문서 조회
  - `query_sql`: 자연어 → SQL 변환 검색

### Changed
- **아키텍처 개선** - 모듈형 설정 시스템으로 전환
- **설정 파일 분리** - `base.yaml`에서 기능별 YAML 파일 imports

---

## [Unreleased]

### Changed
- **Hybrid Search alpha 조정**: 0.6 → 0.5 (Vector/BM25 균형 모드)
  - 문제: 카카오톡 대화 데이터(1,946개 청크)가 RAG 응답에 거의 나타나지 않음
  - 원인: Vector Similarity가 구조화된 FAQ/메타데이터를 선호 (대화체 불리)
  - 해결: BM25(키워드) 가중치 50%로 증가하여 대화체 콘텐츠 검색 개선
  - 설정: `app/config/features/weaviate.yaml` → `hybrid_search.default_alpha`

### Added
- 파일명 PII 마스킹 기능 (`PrivacyMasker.mask_filename()`)

---

## [2025-12-05] - API 응답 파일명 PII 마스킹

### Added
- **파일명 개인정보 마스킹**: API 응답 `sources` 배열에서 고객명(개인명) 자동 마스킹
  - `PrivacyMasker.mask_filename()` 메서드 추가
  - `PrivacyMasker.mask_sources_filenames()` 헬퍼 메서드 추가
  - `RAGPipeline.format_sources()`에 마스킹 로직 통합

### Changed
- `RAGPipeline.__init__()`: `PrivacyMasker` 인스턴스 추가
- `format_sources()`: `document_name` 및 `file_path` 필드에 마스킹 적용

### Security
- 고객 개인정보(개인명) API 응답에서 보호
  - 변환 예시: "홍길동 고객님.txt" → "고객_고객님.txt"
  - 엔티티/브랜드명은 유지: "브랜드A_안내.txt" (변경 없음)

---

## [2025-12-04] - RRF 점수 정규화 및 Top-k 최적화

### Added
- **RRF 점수 100점 정규화**: 0.01~0.04 → 0~100점 변환
  - `app/lib/score_normalizer.py` 모듈 추가
  - `app/config/features/rag.yaml`에 `score_normalization` 섹션 추가

### Changed
- **Top-k 8개로 축소**: 검색 결과 참조 문서 15개 → 8개
  - 토큰 비용 ~47% 절감
  - 응답 속도 개선

---

## [2025-12-02] - 메타데이터 추출 및 검토 시스템

### Added
- **Notion API 직접 연동 메타데이터 추출**
  - `NotionMetadataExtractor`: LLM 기반 구조화 추출
  - 카테고리별 스키마: Category1/Category2/Category3 (예시)

---

## [2025-12-01] - PII Review System

### Added
- **spaCy + Regex 하이브리드 PII 탐지 시스템**
  - `HybridPIIDetector`: 문서 전처리 PII 탐지
  - `PIIPolicyEngine`: 정책 기반 처리 결정
  - `PIIAuditLogger`: MongoDB 감사 로그

### Security
- 전화번호, 이메일, 주소 자동 마스킹
- 주민번호, 카드번호 차단 처리
- 도메인 화이트리스트 (오탐 방지)

---

## [2025-11-28] - OpenRouter 통합

### Changed
- **LLM 통합 아키텍처**: Multi-Provider → OpenRouter 단일 게이트웨이
  - API 키 3개 → 1개로 단순화
  - SDK 의존성 3개 → OpenAI SDK만 사용
  - 통합 비용 추적 및 Fallback 자동 처리

---

## [2025-11-12] - MVP Phase 1

### Added
- RAG 파이프라인 기본 구조
  - 쿼리 확장 → 하이브리드 검색 → 답변 생성
- Self-RAG, LLM Router, Reranking 비활성화 (Phase 2 예정)

---

## 파일 참조

### 최근 변경 파일 (2025-12-05)
- `app/modules/core/privacy/masker.py` - 파일명 마스킹 메서드 추가
- `app/api/services/rag_pipeline.py` - format_sources() 마스킹 적용

### 설정 파일
- `app/config/features/privacy.yaml` - PII 정책 설정
- `app/config/features/rag.yaml` - RAG 파이프라인 설정

---

**관리자**: Claude Code
**마지막 업데이트**: 2026-01-05
