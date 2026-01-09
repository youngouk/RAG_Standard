# 오픈소스화 계획 (Open Source Plan)

본 문서는 현재의 고성능 RAG 시스템을 오픈소스로 배포하기 위한 전략적 방향성과 리팩토링 계획을 기술합니다.

## 핵심 철학 (Philosophy)
- **All-in-One High-Performance RAG**: 최소 기능 제품(MVP)이 아닌, GraphRAG, Agent 등 고급 기능이 모두 통합된 완성형 시스템을 지향합니다.
- **Opinionated Framework**: 모든 툴을 지원하는 범용성보다는, 검증된 최적의 기술 스택(Best Practice)을 제안하고 제공합니다.
- **Service-Oriented**: 라이브러리 형태보다는 즉시 실행 가능한 완성된 애플리케이션(Service) 형태를 유지합니다.

---

## 1. 구조 리팩토링 (기능 통합 및 모듈화)

### 목표
- 기존의 최고급 기능(GraphRAG, Agentic RAG, Semantic Cache 등)을 삭제하지 않고 유지합니다.
- 외부 확장팩(Extension)으로 분리하지 않고, **단일 레포지토리(Monorepo) 내에서 명확하게 모듈화**된 구조를 갖춥니다.

### 실행 방안
- **Internal Modularity**: `app/modules/core` 내부를 기능별(Graph, Retrieval, Agent)로 더 명확히 격리하되, 상호 연동성은 유지합니다.
- **Clean Architecture**: 각 모듈 간의 의존성을 정리하여, 코드가 복잡하게 얽히는 것(Spaghetti Code)을 방지합니다.
- **Stability First**: 분리 배포보다는 통합 배포를 통해 기능 간 호환성과 시스템 안정성을 최우선으로 합니다.

---

## 2. 기술 스택 전략 (Opinionated Adapter)

### 목표
- "모든 것을 지원하는 만능 어댑터"를 지양합니다.
- 개발자가 직접 검증하고 추천하는 **"최적의 조합(Best of Breed)"**을 기본값으로 제공합니다.

### 실행 방안
- **Selected Stack**:
    - **Vector DB**: Weaviate (성능 및 기능 검증됨)
    - **LLM**: Gemini / GPT-4o (검증된 모델)
    - **Reranker**: ColBERT (검증된 성능)
- **Strategic Extensibility**:
    - 무분별한 추상화 대신, 정말 필요한 부분(예: LLM 모델 교체, 프롬프트 템플릿 등)에 한해서만 제한적인 확장 포인트를 제공합니다.
    - 사용자가 "고민하지 않고" 바로 사용할 수 있는 큐레이션 된 경험을 제공합니다.

---

## 3. 배포 형태 (Finished Product)

### 목표
- 라이브러리(`pip install`) 방식이 아닌, **실행 가능한 서비스(Application)** 형태로 배포합니다.
- `Docker Compose` 등을 통해 인프라까지 포함된 **"Turn-key 솔루션"**을 제공합니다.

---

## 4. 리팩토링 계획 (TDD 기반)

> **원칙**: 모든 리팩토링은 기존 테스트가 통과하는 상태에서 진행하며, 변경 전 테스트 추가 → 리팩토링 → 테스트 검증 순서를 따릅니다.

### Phase 1: 레거시/Deprecated 코드 정리 (낮은 위험) ✅ 완료

| 항목 | 파일 | 작업 내용 | 상태 |
|------|------|-----------|------|
| R1.1 | `rerankers/openai_llm_reranker.py` | GPT5NanoReranker → OpenAILLMReranker 리팩토링 (모델 설정 가능) | ✅ 완료 |
| R1.2 | `reranking.yaml` | deprecated 설정 섹션 제거 (gemini_flash, llm) | ✅ 완료 |
| R1.3 | `tools/tool_executor.py` | deprecated `get_tool_executor()` 함수 제거 | ✅ 완료 |
| R1.4 | `retrieval/__init__.py` | OpenAILLMReranker 추가, GPT5NanoReranker는 alias로 유지 | ✅ 완료 |

**변경 사항 요약**:
- `OpenAILLMReranker`: 범용 LLM 리랭커 (model 파라미터로 gpt-5-nano, gpt-4o-mini 등 지정 가능)
- `GPT5NanoReranker`: 하위 호환성 alias (`OpenAILLMReranker`의 별칭)
- `RerankerFactory`: "openai-llm" 프로바이더 등록
- 테스트: 22개 테스트 통과 (10개 신규 + 12개 기존)

**검증 결과**:
```bash
make test-basic  # ✅ 22 passed
make lint-imports  # ✅ 3 contracts KEPT
```

### Phase 2: TODO 항목 해결 (중간 위험) ✅ 완료

| 항목 | 파일 | 작업 내용 | 상태 |
|------|------|-----------|------|
| R2.1 | `config/schemas/__init__.py` | importlib.util 동적 import 제거, 헬퍼 함수 직접 정의 | ✅ 완료 |
| R2.2 | `query_expansion/gpt5_engine.py` | llm_factory 없이 초기화 시 DeprecationWarning 추가 | ✅ 완료 |
| R2.3 | `routing/rule_based_router.py` | _get_default_rules() 단순화 (170줄→55줄), DynamicRuleManager 위임 | ✅ 완료 |

**변경 사항 요약**:
- `schemas/__init__.py`: 레거시 동적 import 제거, BM25Config/PrivacyConfig 직접 정의
- `gpt5_engine.py`: LLM Factory 마이그레이션 유도 (하위 호환성 유지)
- `rule_based_router.py`: 필수 안전 규칙 3개만 유지 (prompt_injection, greeting, thanks)
- 테스트: 13개 신규 테스트 추가

**검증 결과**:
```bash
make test-basic  # ✅ 13 passed (Phase 2 tests)
make lint-imports  # ✅ 3 contracts KEPT
```

### Phase 3: Clean Architecture 강화 (높은 위험) ✅ 완료

| 항목 | 파일 | 작업 내용 | 상태 |
|------|------|-----------|------|
| R3.1 | `modules/core/*` | documents→retrieval re-export 제거, 순환 의존성 테스트 추가 | ✅ 완료 |
| R3.2 | `retrieval/interfaces.py` | Reranker/Retriever/CacheManager Protocol 준수 테스트 (11개) | ✅ 완료 |
| R3.3 | `di_container.py` | AppContainer 문서화 개선, Provider 그룹 테스트 (10개) | ✅ 완료 |

**변경 사항 요약**:
- `documents/__init__.py`: retrieval re-export 제거 (계층 분리)
- `core/__init__.py`: SearchResult, ExpandedQuery → retrieval에서 직접 import
- `di_container.py`: Provider 그룹 다이어그램 추가, 문서화 개선
- 테스트: 25개 아키텍처 테스트 추가 (tests/unit/architecture/)

**검증 결과**:
```bash
uv run pytest tests/unit/architecture/ -v  # ✅ 25 passed
make lint-imports  # ✅ 3 contracts KEPT
```

### 리팩토링 진행 절차 (TDD)

```
1. 기존 테스트 실행 → 모두 통과 확인
2. 변경 대상 코드에 대한 테스트 보강 (없는 경우)
3. 리팩토링 수행 (작은 단위로)
4. 테스트 실행 → 통과 확인
5. 린트/타입체크 실행 → 통과 확인
6. 커밋 (단위별)
```

### 진행 상황 추적

- **마지막 업데이트**: 2026-01-05
- **완료율**: 10/10 항목 (100%) ✅
- **Phase 1**: ✅ 완료 (R1.1 ~ R1.4) - 레거시/Deprecated 코드 정리
- **Phase 2**: ✅ 완료 (R2.1 ~ R2.3) - TODO 항목 해결
- **Phase 3**: ✅ 완료 (R3.1 ~ R3.3) - Clean Architecture 강화
- **다음 작업**: 문서화 계획 및 오픈소스 필수 파일 작성

---

## 5. 문서화 계획 (Post-Refactoring)

### 일정
- 구조 리팩토링(Phase 1~3)이 완전히 종료된 후 진행합니다.

### 내용
- **User Guide**: 완성된 애플리케이션을 띄우고 사용하는 방법.
- **Architecture Overview**: 리팩토링된 내부 모듈 구조 설명.
- **Configuration Guide**: 추천 스택 내에서의 설정 변경 방법.

---

## 6. 오픈소스 필수 파일 (Pre-Release)

| 파일 | 상태 | 비고 |
|------|------|------|
| `LICENSE` | ✅ 완료 | MIT License |
| `README.md` | ✅ 완료 | 기본 내용 포함 |
| `.gitignore` | ✅ 완료 | 민감 정보 제외 |
| `.env.example` | ✅ 완료 | 환경변수 예시 |
| `CONTRIBUTING.md` | ⏸️ 보류 | 기여자 생기면 추가 |
| `CODE_OF_CONDUCT.md` | ⏸️ 보류 | 커뮤니티 커지면 추가 |
| `SECURITY.md` | ⏸️ 보류 | README에 한 줄로 대체 가능 |
| `CHANGELOG.md` | ✅ 완료 | 변경 이력 (v3.1.0) |
| `docker-compose.yml` | ⏸️ 보류 | 클라우드 배포 우선 |
