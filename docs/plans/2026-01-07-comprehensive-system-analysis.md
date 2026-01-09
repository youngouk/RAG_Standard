# RAG_Standard 시스템 종합 구조분석 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** RAG_Standard 시스템 전체를 QA 관점과 개선포인트 발굴 관점에서 완벽하게 분석하여, 기능 검증 및 오픈소스 품질 향상을 달성합니다.

**Architecture:** 16개 병렬 서브에이전트가 각 모듈을 독립적으로 분석 + 2개 종합 분석 에이전트가 전체 결과를 통합합니다. QA 에이전트는 기능 작동 검증에, 개선 에이전트는 코드 품질/구조 개선에 집중합니다.

**Tech Stack:** Python 3.11+, FastAPI, Weaviate, MongoDB, PostgreSQL, LangChain, dependency-injector

---

## 시스템 개요

### 분석 대상 구조

```
RAG_Standard/
├── app/
│   ├── api/                    # API 라우터 및 서비스
│   │   ├── routers/            # 개별 라우터 모듈
│   │   ├── services/           # 비즈니스 로직 서비스
│   │   └── schemas/            # API 스키마 정의
│   ├── core/                   # DI 컨테이너 및 인터페이스
│   ├── config/                 # 설정 스키마
│   ├── infrastructure/         # 스토리지 및 영속성
│   │   ├── persistence/        # PostgreSQL 관련
│   │   └── storage/            # Vector/Metadata 저장소
│   ├── lib/                    # 공통 유틸리티
│   ├── middleware/             # FastAPI 미들웨어
│   ├── models/                 # Pydantic 모델
│   ├── modules/core/           # 핵심 비즈니스 로직
│   │   ├── agent/              # Agentic RAG 오케스트레이터
│   │   ├── documents/          # 문서 처리 (로더, 청킹)
│   │   ├── embedding/          # 임베딩 생성
│   │   ├── enrichment/         # 컨텍스트 강화
│   │   ├── evaluation/         # 평가 시스템
│   │   ├── generation/         # LLM 응답 생성
│   │   ├── graph/              # GraphRAG (지식 그래프)
│   │   ├── mcp/                # Model Context Protocol
│   │   ├── privacy/            # PII 처리 및 마스킹
│   │   ├── retrieval/          # 검색 (하이브리드, 리랭킹)
│   │   ├── routing/            # 쿼리 라우팅
│   │   ├── self_rag/           # Self-RAG 품질 게이트
│   │   ├── session/            # 세션 관리
│   │   ├── sql_search/         # SQL 기반 검색
│   │   └── tools/              # 외부 도구 통합
│   ├── batch/                  # 배치 처리
│   └── modules/ingestion/      # 데이터 적재
├── tests/                      # 테스트 (111개 파일, 1082개 테스트)
└── docs/                       # 문서
```

### 분석 목표

1. **QA 관점 (기능 검증)**
   - 각 모듈이 의도된 대로 작동하는가?
   - 에러 처리가 적절한가?
   - 엣지 케이스가 커버되는가?
   - 테스트 커버리지가 충분한가?

2. **개선 관점 (품질 향상)**
   - 코드 중복이 있는가?
   - 아키텍처 개선 여지가 있는가?
   - 성능 최적화 포인트는?
   - 유지보수성 개선 방안은?

---

## Part A: QA 분석 에이전트 (기능 검증)

### Task 1: API Layer QA Agent

**Files:**
- Analyze: `app/api/routers/*.py`
- Analyze: `app/api/services/*.py`
- Analyze: `app/api/schemas/*.py`
- Test Reference: `tests/unit/api/**/*.py`

**Step 1: API 라우터 기능 검증**

서브에이전트 프롬프트:
```
당신은 QA 전문가입니다. app/api/ 디렉토리의 모든 API 엔드포인트를 분석하세요.

분석 항목:
1. 각 엔드포인트의 입력/출력 스키마 검증
2. 에러 핸들링 패턴 검증 (HTTPException 사용, 에러 코드 일관성)
3. 인증/인가 로직 검증 (API Key, Rate Limiting)
4. 비동기 처리 패턴 검증 (async/await, 데드락 가능성)
5. 의존성 주입 검증 (Depends 사용, 순환 참조)

결과 형식:
- PASS: 정상 작동 확인된 항목
- WARN: 잠재적 문제 (작동하지만 개선 필요)
- FAIL: 기능 오류 또는 미구현
```

**Step 2: 테스트 커버리지 분석**

Run: `pytest tests/unit/api/ --cov=app/api --cov-report=term-missing -v`
Expected: 각 엔드포인트별 커버리지 비율 확인

**Step 3: 결과 문서화**

Output: `analysis-results/api-layer-qa.md`

---

### Task 2: Retrieval Module QA Agent

**Files:**
- Analyze: `app/modules/core/retrieval/orchestrator.py`
- Analyze: `app/modules/core/retrieval/retrievers/*.py`
- Analyze: `app/modules/core/retrieval/rerankers/*.py`
- Analyze: `app/modules/core/retrieval/cache/*.py`
- Analyze: `app/modules/core/retrieval/query_expansion/*.py`
- Analyze: `app/modules/core/retrieval/bm25/*.py`
- Analyze: `app/modules/core/retrieval/hybrid_search/*.py`
- Test Reference: `tests/unit/retrieval/**/*.py`

**Step 1: 검색 파이프라인 기능 검증**

서브에이전트 프롬프트:
```
당신은 검색 시스템 QA 전문가입니다. retrieval 모듈 전체를 분석하세요.

분석 항목:
1. RetrievalOrchestrator의 검색 흐름 검증
   - Dense(벡터) + Sparse(BM25) 하이브리드 검색
   - GraphRAG 통합 검색
   - Semantic Cache 동작
2. Reranker Chain 검증 (ColBERT, Jina, Gemini)
3. Query Expansion 동작 검증
4. 캐시 일관성 검증 (Memory Cache, Semantic Cache)
5. 에러 복구 패턴 (Fallback 로직)

결과 형식:
- 검색 정확도 관련 잠재 이슈
- 성능 병목점
- 에러 처리 미흡 지점
```

**Step 2: 테스트 실행**

Run: `pytest tests/unit/retrieval/ -v --tb=short`
Expected: 모든 테스트 PASS

**Step 3: 결과 문서화**

Output: `analysis-results/retrieval-qa.md`

---

### Task 3: Generation Module QA Agent

**Files:**
- Analyze: `app/modules/core/generation/generator.py`
- Analyze: `app/modules/core/generation/prompt_manager.py`
- Analyze: `app/modules/core/generation/providers/*.py`
- Test Reference: `tests/unit/generation/**/*.py`

**Step 1: 응답 생성 기능 검증**

서브에이전트 프롬프트:
```
당신은 LLM 통합 QA 전문가입니다. generation 모듈을 분석하세요.

분석 항목:
1. Multi-Provider Fallback 로직 검증 (GPT → Claude → Gemini)
2. Prompt Template 관리 검증
3. 스트리밍 응답 처리 검증
4. 토큰 제한 처리 검증
5. 타임아웃 및 재시도 로직

결과 형식:
- Provider 전환 시나리오별 동작 확인
- 에러 시 사용자 경험 영향 분석
```

**Step 2: 테스트 실행**

Run: `pytest tests/unit/generation/ -v`
Expected: Fallback 시나리오 테스트 포함

---

### Task 4: GraphRAG Module QA Agent

**Files:**
- Analyze: `app/modules/core/graph/builder.py`
- Analyze: `app/modules/core/graph/stores/*.py`
- Analyze: `app/modules/core/graph/extractors/*.py`
- Test Reference: `tests/unit/graph/**/*.py`

**Step 1: 지식 그래프 기능 검증**

서브에이전트 프롬프트:
```
당신은 GraphRAG 전문가입니다. graph 모듈을 분석하세요.

분석 항목:
1. KnowledgeGraphBuilder 동작 검증
2. Entity/Relation Extractor 정확도
3. NetworkX Store vs Neo4j Store 호환성
4. 벡터 검색 통합 ("SAMSUNG" → "삼성전자" 매핑)
5. 그래프 쿼리 성능

결과 형식:
- 엔티티 추출 정확도 이슈
- 관계 추론 누락 케이스
- 스토어 간 일관성 문제
```

---

### Task 5: Privacy Module QA Agent

**Files:**
- Analyze: `app/modules/core/privacy/processor.py`
- Analyze: `app/modules/core/privacy/masker.py`
- Analyze: `app/modules/core/privacy/review/*.py`
- Test Reference: `tests/unit/privacy/**/*.py`

**Step 1: PII 처리 기능 검증**

서브에이전트 프롬프트:
```
당신은 개인정보보호 QA 전문가입니다. privacy 모듈을 분석하세요.

분석 항목:
1. PII 탐지 정확도 (한국어 이름, 전화번호, 주민번호 등)
2. 마스킹 일관성 (동일 PII → 동일 마스크)
3. Whitelist 동작 검증 (허용된 데이터 통과)
4. 감사 로그 기록 검증
5. 답변 및 소스 미리보기 마스킹

결과 형식:
- 탐지 누락 패턴
- 과잉 마스킹 패턴
- 보안 취약점
```

---

### Task 6: Session Module QA Agent

**Files:**
- Analyze: `app/modules/core/session/manager.py`
- Analyze: `app/modules/core/session/services/*.py`
- Test Reference: `tests/unit/session/**/*.py` (if exists)

**Step 1: 세션 관리 기능 검증**

서브에이전트 프롬프트:
```
당신은 세션 관리 QA 전문가입니다. session 모듈을 분석하세요.

분석 항목:
1. 세션 생성/조회/삭제 CRUD 검증
2. 세션 만료 로직 검증
3. 대화 히스토리 관리 검증
4. MongoDB 연결 안정성
5. 동시성 처리 (Race Condition)

결과 형식:
- 세션 누수 가능성
- 메모리 관리 이슈
- 동시 접근 문제
```

---

### Task 7: Agent Module QA Agent

**Files:**
- Analyze: `app/modules/core/agent/orchestrator.py`
- Analyze: `app/modules/core/agent/planner.py`
- Analyze: `app/modules/core/agent/executor.py`
- Test Reference: `tests/unit/agent/**/*.py`

**Step 1: Agentic RAG 기능 검증**

서브에이전트 프롬프트:
```
당신은 AI Agent 전문가입니다. agent 모듈을 분석하세요.

분석 항목:
1. Plan-Execute 패턴 동작 검증
2. Tool Selection 로직 검증
3. 중간 결과 합성 검증
4. 재귀적 실행 제한 검증
5. 에러 복구 및 롤백

결과 형식:
- 무한 루프 가능성
- Tool 호출 실패 처리
- 응답 품질 이슈
```

---

### Task 8: MCP Module QA Agent

**Files:**
- Analyze: `app/modules/core/mcp/server.py`
- Analyze: `app/modules/core/mcp/tools/*.py`
- Test Reference: `tests/unit/mcp/**/*.py`

**Step 1: MCP 서버 기능 검증**

서브에이전트 프롬프트:
```
당신은 MCP(Model Context Protocol) 전문가입니다. mcp 모듈을 분석하세요.

분석 항목:
1. MCP 서버 초기화 및 연결 검증
2. Tool 등록 및 호출 검증
3. Weaviate Tools 동작 검증
4. Graph Tools 동작 검증
5. 에러 핸들링 및 타임아웃

결과 형식:
- Tool 호출 실패 시나리오
- 연결 불안정 처리
- 보안 검증
```

---

### Task 9: Document Processing QA Agent

**Files:**
- Analyze: `app/modules/core/documents/loaders/*.py`
- Analyze: `app/modules/core/documents/chunking/*.py`
- Analyze: `app/modules/core/documents/processors/*.py`
- Test Reference: `tests/unit/documents/**/*.py` (if exists)

**Step 1: 문서 처리 기능 검증**

서브에이전트 프롬프트:
```
당신은 문서 처리 QA 전문가입니다. documents 모듈을 분석하세요.

분석 항목:
1. 파일 형식별 로더 동작 (PDF, DOCX, XLSX, CSV, JSON, MD, HTML)
2. 청킹 전략 검증 (시맨틱, 포인트 룰)
3. 메타데이터 추출 정확도
4. 인코딩 처리 (한국어, UTF-8)
5. 대용량 파일 처리

결과 형식:
- 파싱 실패 케이스
- 청킹 품질 이슈
- 메모리 사용량 문제
```

---

### Task 10: Evaluation Module QA Agent

**Files:**
- Analyze: `app/modules/core/evaluation/evaluator.py`
- Analyze: `app/modules/core/evaluation/factory.py`
- Test Reference: `tests/unit/evaluation/**/*.py`

**Step 1: 평가 시스템 기능 검증**

서브에이전트 프롬프트:
```
당신은 RAG 평가 시스템 전문가입니다. evaluation 모듈을 분석하세요.

분석 항목:
1. 내부 평가자 동작 검증
2. RAGAS 통합 검증 (선택적)
3. 평가 지표 계산 정확도
4. 배치 평가 동작
5. 결과 저장 및 조회

결과 형식:
- 평가 편향 가능성
- 메트릭 계산 오류
- 성능 병목
```

---

### Task 11: Infrastructure QA Agent

**Files:**
- Analyze: `app/infrastructure/persistence/*.py`
- Analyze: `app/infrastructure/storage/**/*.py`
- Analyze: `app/lib/weaviate_client.py`
- Analyze: `app/lib/mongodb_client.py`

**Step 1: 인프라 연결 검증**

서브에이전트 프롬프트:
```
당신은 인프라 QA 전문가입니다. infrastructure 및 lib 모듈을 분석하세요.

분석 항목:
1. PostgreSQL 연결 관리 검증
2. MongoDB 연결 관리 검증
3. Weaviate 연결 관리 검증
4. Connection Pooling 검증
5. 리소스 정리 (cleanup) 검증

결과 형식:
- 연결 누수 가능성
- 타임아웃 처리
- Graceful Shutdown
```

---

### Task 12: DI Container QA Agent

**Files:**
- Analyze: `app/core/di_container.py`
- Analyze: `app/core/interfaces/*.py`
- Test Reference: `tests/unit/architecture/**/*.py`

**Step 1: 의존성 주입 검증**

서브에이전트 프롬프트:
```
당신은 DI(Dependency Injection) 전문가입니다. core 모듈을 분석하세요.

분석 항목:
1. Provider 타입별 동작 검증 (Singleton, Factory, Coroutine)
2. 비동기 초기화 순서 검증
3. 리소스 정리 순서 검증
4. 순환 의존성 검증
5. 인터페이스 준수 검증

결과 형식:
- 초기화 순서 문제
- 리소스 정리 누락
- 타입 안전성 이슈
```

---

## Part B: 개선포인트 발굴 에이전트

### Task 13: Architecture Improvement Agent

**Files:**
- Analyze: 전체 `app/` 디렉토리 구조
- Reference: `docs/ARCHITECTURE.md`

**Step 1: 아키텍처 분석**

서브에이전트 프롬프트:
```
당신은 소프트웨어 아키텍트입니다. RAG_Standard의 전체 아키텍처를 분석하세요.

분석 항목:
1. 계층 분리 평가 (API → Service → Domain → Infrastructure)
2. 모듈 응집도 분석
3. 의존성 방향 검증 (Clean Architecture 원칙)
4. 확장성 평가 (새 기능 추가 용이성)
5. 테스트 용이성 평가

개선 제안 형식:
- 현재 상태 설명
- 문제점
- 개선 방안
- 예상 영향도 (High/Medium/Low)
- 구현 복잡도 (High/Medium/Low)
```

---

### Task 14: Code Quality Improvement Agent

**Files:**
- Analyze: `app/**/*.py` (전체 소스 코드)
- Tools: ruff, mypy 결과 분석

**Step 1: 코드 품질 분석**

서브에이전트 프롬프트:
```
당신은 코드 품질 전문가입니다. RAG_Standard의 코드 품질을 분석하세요.

분석 항목:
1. 코드 중복 탐지 (DRY 원칙)
2. 복잡도 분석 (순환 복잡도, 인지 복잡도)
3. 타입 안전성 평가 (mypy 결과)
4. 코딩 컨벤션 준수 (ruff 결과)
5. 문서화 수준 (docstring 커버리지)

개선 제안 형식:
- 발견된 이슈
- 우선순위 (Critical/High/Medium/Low)
- 개선 방안
- 자동 수정 가능 여부
```

**Step 2: 정적 분석 실행**

Run: `ruff check app/ --statistics`
Run: `mypy app/ --ignore-missing-imports`

---

### Task 15: Performance Optimization Agent

**Files:**
- Analyze: `app/modules/core/retrieval/orchestrator.py`
- Analyze: `app/modules/core/generation/generator.py`
- Analyze: `app/api/services/rag_pipeline.py`

**Step 1: 성능 분석**

서브에이전트 프롬프트:
```
당신은 성능 최적화 전문가입니다. RAG_Standard의 성능 병목점을 분석하세요.

분석 항목:
1. 검색 파이프라인 레이턴시 분석
2. LLM 호출 최적화 (배칭, 캐싱)
3. 데이터베이스 쿼리 최적화
4. 메모리 사용량 분석
5. 동시성 처리 효율성

개선 제안 형식:
- 병목 지점
- 현재 성능 (추정)
- 개선 방안
- 예상 개선율
- 구현 복잡도
```

---

### Task 16: Security Audit Agent

**Files:**
- Analyze: `app/lib/auth.py`
- Analyze: `app/middleware/*.py`
- Analyze: `app/modules/core/privacy/*.py`
- Analyze: 환경 변수 처리 코드

**Step 1: 보안 감사**

서브에이전트 프롬프트:
```
당신은 보안 감사 전문가입니다. RAG_Standard의 보안 취약점을 분석하세요.

분석 항목:
1. 인증/인가 메커니즘 검증
2. 입력 검증 (Injection 방지)
3. 민감 데이터 처리 (PII, API Key)
4. 에러 메시지 정보 노출
5. 의존성 취약점 (CVE 검사)

개선 제안 형식:
- 취약점 유형
- 심각도 (Critical/High/Medium/Low)
- 영향 범위
- 개선 방안
- OWASP 참조
```

---

### Task 17: Test Coverage Improvement Agent

**Files:**
- Analyze: `tests/**/*.py`
- Reference: 커버리지 리포트

**Step 1: 테스트 분석**

서브에이전트 프롬프트:
```
당신은 테스트 전문가입니다. RAG_Standard의 테스트 전략을 분석하세요.

분석 항목:
1. 테스트 커버리지 분석 (라인, 브랜치)
2. 테스트 유형 분포 (단위/통합/E2E)
3. Mock 사용 패턴 분석
4. 엣지 케이스 커버리지
5. 테스트 실행 시간 분석

개선 제안 형식:
- 커버리지 갭
- 누락된 테스트 케이스
- 테스트 품질 이슈
- 추천 테스트 추가
```

**Step 2: 커버리지 실행**

Run: `pytest tests/ --cov=app --cov-report=html --cov-report=term`

---

### Task 18: Documentation Improvement Agent

**Files:**
- Analyze: `docs/*.md`
- Analyze: `README.md`
- Analyze: 코드 내 docstring

**Step 1: 문서화 분석**

서브에이전트 프롬프트:
```
당신은 기술 문서 전문가입니다. RAG_Standard의 문서화 수준을 분석하세요.

분석 항목:
1. README 완성도
2. API 문서화 수준 (OpenAPI)
3. 아키텍처 문서 정확성
4. 설정 가이드 완성도
5. 코드 주석 품질

개선 제안 형식:
- 누락된 문서
- 업데이트 필요 문서
- 예제 부족 영역
- 다국어 지원 필요성
```

---

## Part C: 종합 분석 에이전트

### Task 19: QA Summary Aggregator

**Dependencies:** Task 1-12 결과

**Step 1: QA 결과 종합**

서브에이전트 프롬프트:
```
당신은 QA 리드입니다. Task 1-12의 QA 분석 결과를 종합하세요.

종합 항목:
1. 전체 기능 검증 상태 요약 (PASS/WARN/FAIL 통계)
2. 모듈별 품질 점수 (1-10)
3. Critical 이슈 목록 (즉시 수정 필요)
4. High 이슈 목록 (1주 내 수정 권장)
5. 테스트 커버리지 종합

최종 산출물:
- analysis-results/qa-summary.md
- 모듈별 품질 대시보드
- 권장 수정 우선순위
```

---

### Task 20: Improvement Roadmap Generator

**Dependencies:** Task 13-18 결과

**Step 1: 개선 로드맵 생성**

서브에이전트 프롬프트:
```
당신은 기술 PM입니다. Task 13-18의 개선 제안을 종합하여 로드맵을 생성하세요.

종합 항목:
1. 개선 제안 분류 (아키텍처/품질/성능/보안/테스트/문서)
2. 영향도 × 복잡도 매트릭스
3. 단기 개선 (1-2주)
4. 중기 개선 (1개월)
5. 장기 개선 (분기)

최종 산출물:
- analysis-results/improvement-roadmap.md
- 우선순위 매트릭스
- 예상 투입 리소스
```

---

## 실행 가이드

### 병렬 실행 그룹

**Group 1 (QA - 동시 실행 가능):**
- Task 1: API Layer QA
- Task 2: Retrieval Module QA
- Task 3: Generation Module QA
- Task 4: GraphRAG Module QA
- Task 5: Privacy Module QA
- Task 6: Session Module QA

**Group 2 (QA - 동시 실행 가능):**
- Task 7: Agent Module QA
- Task 8: MCP Module QA
- Task 9: Document Processing QA
- Task 10: Evaluation Module QA
- Task 11: Infrastructure QA
- Task 12: DI Container QA

**Group 3 (개선 - 동시 실행 가능):**
- Task 13: Architecture Improvement
- Task 14: Code Quality Improvement
- Task 15: Performance Optimization
- Task 16: Security Audit
- Task 17: Test Coverage Improvement
- Task 18: Documentation Improvement

**Group 4 (종합 - 순차 실행):**
- Task 19: QA Summary (Group 1, 2 완료 후)
- Task 20: Improvement Roadmap (Group 3 완료 후)

### 결과물 디렉토리

```
analysis-results/
├── qa/
│   ├── api-layer-qa.md
│   ├── retrieval-qa.md
│   ├── generation-qa.md
│   ├── graphrag-qa.md
│   ├── privacy-qa.md
│   ├── session-qa.md
│   ├── agent-qa.md
│   ├── mcp-qa.md
│   ├── documents-qa.md
│   ├── evaluation-qa.md
│   ├── infrastructure-qa.md
│   └── di-container-qa.md
├── improvements/
│   ├── architecture.md
│   ├── code-quality.md
│   ├── performance.md
│   ├── security.md
│   ├── test-coverage.md
│   └── documentation.md
├── qa-summary.md
└── improvement-roadmap.md
```

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-01-07-comprehensive-system-analysis.md`.**

Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
