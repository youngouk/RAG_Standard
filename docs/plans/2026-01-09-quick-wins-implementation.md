# Quick Wins 구현 계획 (4개 작업)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 난이도 대비 임팩트가 좋은 4개 개선 작업을 서브에이전트로 병렬 실행하여 시스템 완성도 향상

**Architecture:** 토큰 최적화를 위해 코드 변경 작업(Task 1, 3)에만 코드 리뷰 적용, 문서화 작업(Task 2, 4)은 리뷰 생략

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Markdown

---

## 서브에이전트 구성 전략

| Task | 유형 | 코드 리뷰 | 사유 |
|------|------|----------|------|
| Task 1 | 코드 변경 | ✅ 필요 | 캐시 메트릭 확장 - 프로덕션 코드 수정 |
| Task 2 | 문서 작성 | ❌ 불필요 | README 개선 - 문서만 수정 |
| Task 3 | 코드 변경 | ✅ 필요 | 모니터링 확장 - 프로덕션 코드 수정 |
| Task 4 | 문서 작성 | ❌ 불필요 | API 참조 문서 - 신규 문서 작성 |

**예상 토큰 절약:** 리뷰 2회 생략으로 약 30-40% 토큰 절감

---

## Task 1: 캐시 히트율 모니터링 대시보드 노출

**유형:** 코드 변경 (코드 리뷰 필요)

**Files:**
- Modify: `app/api/health.py:161-189` (cache-stats 엔드포인트 확장)
- Modify: `app/api/admin.py:288-320` (realtime-metrics에 캐시 추가)
- Test: `tests/unit/api/test_health.py` (기존 테스트 확장)

**현재 상태:**
- 캐시 히트율은 이미 `get_stats()`로 수집됨
- `/health/cache-stats`에서 일부 노출
- `/api/admin/realtime-metrics`에는 캐시 정보 없음

**Step 1: realtime-metrics에 캐시 메트릭 추가**

`app/api/admin.py`의 `get_realtime_metrics()` 함수 수정 (라인 288-320):

```python
# 기존 응답에 캐시 메트릭 추가
@router.get("/realtime-metrics", response_model=RealtimeMetrics)
async def get_realtime_metrics(
    retrieval_module: RetrievalModule = Depends(get_retrieval_module),
) -> RealtimeMetrics:
    """실시간 모니터링 메트릭 조회"""

    # 기존 메트릭 수집
    stats = retrieval_module.get_stats() if hasattr(retrieval_module, "get_stats") else {}
    orchestrator_stats = stats.get("orchestrator", {})
    cache_stats = stats.get("cache", {})

    # 캐시 메트릭 추가
    cache_hit_rate = orchestrator_stats.get("cache_hit_rate", 0.0)
    cache_hits = orchestrator_stats.get("cache_hits", 0)
    cache_misses = orchestrator_stats.get("cache_misses", 0)
    saved_time_ms = cache_stats.get("saved_time_ms", 0)

    return RealtimeMetrics(
        timestamp=datetime.now(UTC).isoformat(),
        chat_requests_per_minute=...,  # 기존 유지
        average_response_time=...,      # 기존 유지
        active_sessions=...,            # 기존 유지
        memory_usage_mb=...,            # 기존 유지
        cpu_usage_percent=...,          # 기존 유지
        error_rate=...,                 # 기존 유지
        # 신규 추가
        cache_hit_rate=cache_hit_rate,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        cache_saved_time_ms=saved_time_ms,
    )
```

**Step 2: RealtimeMetrics 모델 확장**

`app/api/admin.py`의 RealtimeMetrics 클래스 수정 (라인 55-64):

```python
class RealtimeMetrics(BaseModel):
    """실시간 메트릭 응답 모델"""
    timestamp: str
    chat_requests_per_minute: int
    average_response_time: float
    active_sessions: int
    memory_usage_mb: float
    cpu_usage_percent: float
    error_rate: float
    # 캐시 메트릭 추가
    cache_hit_rate: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_saved_time_ms: float = 0.0
```

**Step 3: 테스트 실행**

Run: `ENVIRONMENT=test pytest tests/unit/api/test_health.py -v`

Expected: 모든 테스트 통과

**Step 4: 전체 테스트 검증**

Run: `ENVIRONMENT=test make test`

Expected: 1,129개 테스트 통과

**Step 5: 커밋**

```bash
git add app/api/admin.py
git commit -m "기능: 실시간 메트릭에 캐시 히트율 추가"
```

---

## Task 2: README Quick Start 통합 개선

**유형:** 문서 작성 (코드 리뷰 불필요)

**Files:**
- Modify: `README.md`

**현재 상태:**
- Quick Start가 4줄로 너무 간단
- 사전 요구사항 체크 없음
- .env 설정 단계 누락
- Swagger UI 접근 방법 미기재

**Step 1: README.md Quick Start 섹션 확장**

현재 (라인 약 30-40):
```markdown
## 빠른 시작

```bash
uv sync
docker compose -f docker-compose.weaviate.yml up -d
make test
make dev-reload
```
```

변경 후:
```markdown
## 빠른 시작 (5분)

### 사전 요구사항
- Python 3.11 이상 (`python --version`)
- Docker & Docker Compose (`docker --version`)
- UV 패키지 매니저 (`uv --version` - 없으면 `pip install uv`)

### Step 1: 설치 (2분)
```bash
git clone https://github.com/your-repo/RAG_Standard.git
cd RAG_Standard
uv sync  # 모든 의존성 자동 설치 (spaCy 한국어 모델 포함)
```

### Step 2: 환경 설정 (1분)
```bash
cp .env.example .env
# .env 파일에서 최소 1개 LLM API 키 설정:
# - GOOGLE_API_KEY (권장, 무료 티어 제공)
# - 또는 OPENAI_API_KEY / ANTHROPIC_API_KEY
```

### Step 3: 인프라 실행 (1분)
```bash
docker compose -f docker-compose.weaviate.yml up -d
```

### Step 4: 서버 실행
```bash
make dev-reload  # 개발 서버 (자동 리로드)
```

### Step 5: 검증
- **API 문서**: http://localhost:8000/docs (Swagger UI)
- **헬스 체크**: http://localhost:8000/health

### 테스트 실행
```bash
ENVIRONMENT=test make test  # 1,129개 테스트
```

> 📖 상세 설정: [docs/SETUP.md](docs/SETUP.md) 참조
```

**Step 2: 커밋**

```bash
git add README.md
git commit -m "문서: README Quick Start 가이드 상세화"
```

---

## Task 3: 모니터링 대시보드 LLM 비용 통합

**유형:** 코드 변경 (코드 리뷰 필요)

**Files:**
- Modify: `app/api/admin.py:288-320` (realtime-metrics에 비용 추가)
- Test: `tests/unit/api/test_monitoring.py`

**현재 상태:**
- `/monitoring/costs`에서 비용 조회 가능
- `/api/admin/realtime-metrics`에는 비용 정보 없음
- 한 곳에서 모든 핵심 메트릭 확인 불가

**Step 1: CostTracker 통합**

`app/api/admin.py`의 `get_realtime_metrics()` 수정:

```python
from app.core.di_container import AppContainer

@router.get("/realtime-metrics", response_model=RealtimeMetrics)
async def get_realtime_metrics(
    retrieval_module: RetrievalModule = Depends(get_retrieval_module),
) -> RealtimeMetrics:
    """실시간 모니터링 메트릭 조회"""
    container = _get_container()
    cost_tracker = container.cost_tracker()

    # 비용 요약
    cost_summary = cost_tracker.get_summary()

    return RealtimeMetrics(
        # ... 기존 필드 ...
        # 비용 메트릭 추가
        total_cost_usd=cost_summary.get("total_cost_usd", 0.0),
        cost_per_hour=cost_summary.get("cost_per_hour", 0.0),
        total_llm_tokens=cost_summary.get("total_tokens", 0),
    )
```

**Step 2: RealtimeMetrics 모델에 비용 필드 추가**

```python
class RealtimeMetrics(BaseModel):
    # ... 기존 필드 ...
    # 비용 메트릭
    total_cost_usd: float = 0.0
    cost_per_hour: float = 0.0
    total_llm_tokens: int = 0
```

**Step 3: 테스트 실행**

Run: `ENVIRONMENT=test pytest tests/unit/api/ -v -k "metrics or monitoring"`

Expected: 관련 테스트 통과

**Step 4: 전체 테스트 검증**

Run: `ENVIRONMENT=test make test`

Expected: 1,129개 테스트 통과

**Step 5: 커밋**

```bash
git add app/api/admin.py
git commit -m "기능: 실시간 메트릭에 LLM 비용 정보 추가"
```

---

## Task 4: API 참조 문서 작성

**유형:** 문서 작성 (코드 리뷰 불필요)

**Files:**
- Create: `docs/API_REFERENCE.md`
- Modify: `docs/README.md` (링크 추가)

**Step 1: API 참조 문서 생성**

`docs/API_REFERENCE.md` 생성:

```markdown
# RAG_Standard API 참조

> 모든 API는 http://localhost:8000/docs (Swagger UI)에서 대화형으로 테스트 가능합니다.

## 인증

### API 키 인증
관리자 API (`/api/admin/*`)는 `X-API-Key` 헤더 인증이 필요합니다.

```bash
curl -H "X-API-Key: YOUR_FASTAPI_AUTH_KEY" \
  http://localhost:8000/api/admin/status
```

---

## 핵심 API

### POST /api/chat
RAG 기반 채팅 요청

**Request:**
```json
{
  "message": "삼성전자 주가 전망은?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "삼성전자의 주가 전망에 대해...",
  "sources": [...],
  "session_id": "generated-or-provided-id"
}
```

---

### GET /health
시스템 헬스 체크

**Response:**
```json
{
  "status": "OK",
  "uptime": 3600.5,
  "timestamp": "2026-01-09T15:30:00Z"
}
```

---

### GET /api/admin/status
시스템 전체 상태 조회 (인증 필요)

**Headers:** `X-API-Key: YOUR_KEY`

**Response:**
```json
{
  "status": "healthy",
  "modules": {
    "session": true,
    "retrieval": true,
    "generation": true
  },
  "memory_usage": {...},
  "active_sessions": 5,
  "total_documents": 1000
}
```

---

### GET /api/admin/realtime-metrics
실시간 모니터링 메트릭 (인증 필요)

**Headers:** `X-API-Key: YOUR_KEY`

**Response:**
```json
{
  "timestamp": "2026-01-09T15:30:00Z",
  "chat_requests_per_minute": 10,
  "average_response_time": 1.5,
  "cache_hit_rate": 0.65,
  "total_cost_usd": 0.15,
  "error_rate": 0.01
}
```

---

### POST /api/ingest/documents
문서 인덱싱 (인증 필요)

**Headers:** `X-API-Key: YOUR_KEY`

**Request:**
```json
{
  "documents": [
    {
      "content": "문서 내용...",
      "metadata": {"source": "manual"}
    }
  ]
}
```

---

## 전체 엔드포인트 목록

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| GET | /health | 헬스 체크 | ❌ |
| GET | /health/stats | 시스템 통계 | ❌ |
| POST | /api/chat | 채팅 요청 | ❌ |
| GET | /api/admin/status | 시스템 상태 | ✅ |
| GET | /api/admin/realtime-metrics | 실시간 메트릭 | ✅ |
| POST | /api/ingest/documents | 문서 인덱싱 | ✅ |
| GET | /monitoring/metrics | 성능 메트릭 | ❌ |
| GET | /monitoring/costs | 비용 통계 | ❌ |

> 📖 상세 스키마 및 모든 파라미터: [Swagger UI](/docs)
```

**Step 2: docs/README.md에 링크 추가**

```markdown
## 문서 목록
- [API 참조](API_REFERENCE.md) - 엔드포인트 및 사용 예시
```

**Step 3: 커밋**

```bash
git add docs/API_REFERENCE.md docs/README.md
git commit -m "문서: API 참조 문서 추가"
```

---

## Task 5: 최종 검증 및 푸시

**Step 1: 전체 품질 검사**

```bash
make lint && make type-check
```

Expected: 모두 통과

**Step 2: 전체 테스트**

```bash
ENVIRONMENT=test make test
```

Expected: 1,129개+ 테스트 통과

**Step 3: 커밋 스쿼시 (선택)**

```bash
git rebase -i HEAD~4  # 4개 커밋을 정리 (선택사항)
```

**Step 4: 푸시**

```bash
git push origin main
```

---

## 실행 순서 권장

**병렬 실행 가능:**
- Task 1 + Task 2 (서로 독립적)
- Task 3 + Task 4 (서로 독립적)

**권장 순서:**
1. Task 2 (문서) → 가장 간단, 코드 충돌 없음
2. Task 4 (문서) → 신규 파일 생성, 충돌 없음
3. Task 1 (코드) → admin.py 수정
4. Task 3 (코드) → Task 1과 같은 파일 수정 (순차 필요)
5. Task 5 (검증) → 최종 확인

---

## 리스크 및 롤백

**리스크:**
- Task 1, 3: RealtimeMetrics 스키마 변경으로 기존 클라이언트 영향 가능 (하위 호환 유지됨)

**롤백:**
```bash
git revert HEAD~N  # N = 되돌릴 커밋 수
```
