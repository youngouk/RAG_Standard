# LLM 문서 보강 (Enrichment) 모듈

문서 로드 시 LLM을 사용하여 메타데이터를 자동으로 생성하는 기능입니다.

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [설정 방법](#설정-방법)
- [사용 방법](#사용-방법)
- [테스트](#테스트)
- [문제 해결](#문제-해결)

---

## 개요

고객 상담 데이터를 LLM으로 분석하여 다음 메타데이터를 자동 생성합니다:

- **category_main**: 주요 카테고리 (예: "보너스기능", "결제", "회원관리")
- **category_sub**: 세부 카테고리 (예: "친구초대", "결제오류")
- **intent**: 사용자 의도 (예: "기능 설명 요청")
- **consult_type**: 상담 유형 (예: "초대코드문의")
- **keywords**: 핵심 키워드 리스트
- **summary**: 한 줄 요약
- **is_tool_related**: 도구 관련 여부
- **requires_db_check**: DB 확인 필요 여부

---

## 주요 기능

### ✅ 핵심 기능

1. **LLM 기반 보강**: gpt-4o-mini 사용
2. **배치 처리**: 10개씩 묶어서 처리 (성능 최적화)
3. **Graceful Degradation**: 실패 시 원본 문서 사용
4. **재시도 로직**: Exponential Backoff 적용
5. **타임아웃 관리**: 단건 30초, 배치 90초

### 🔒 안전장치

- **기본값 false**: `enrichment.enabled: false`로 시작
- **Null Object 패턴**: 비활성화 시 NullEnricher 사용
- **에러 격리**: 보강 실패해도 파이프라인 정상 동작
- **토큰 추적**: 사용량 및 비용 모니터링

---

## 아키텍처

### 구조도

```
EnrichmentService (오케스트레이션)
    ├── EnricherInterface (추상 인터페이스)
    │   ├── NullEnricher (비활성화 시)
    │   └── LLMEnricher (활성화 시)
    ├── EnrichmentSchema (Pydantic 모델)
    └── Prompts (프롬프트 템플릿)
```

### 디렉토리 구조

```
app/modules/core/enrichment/
├── __init__.py
├── README.md                        # 이 파일
├── interfaces/
│   └── enricher_interface.py       # 추상 인터페이스
├── enrichers/
│   ├── null_enricher.py            # 비활성화 구현체
│   └── llm_enricher.py             # LLM 보강 구현체
├── schemas/
│   └── enrichment_schema.py        # Pydantic 모델
├── prompts/
│   └── enrichment_prompts.py       # 프롬프트 템플릿
└── services/
    └── enrichment_service.py       # 오케스트레이션
```

---

## 설정 방법

### 1. 환경 변수 설정 (.env)

```bash
# 보강 기능 활성화 (기본값: false)
ENRICHMENT_ENABLED=false

# LLM 모델 (기본값: gpt-4o-mini)
ENRICHMENT_LLM_MODEL=gpt-4o-mini

# 온도 (기본값: 0.1)
ENRICHMENT_LLM_TEMPERATURE=0.1

# 배치 크기 (기본값: 10)
ENRICHMENT_BATCH_SIZE=10

# OpenAI API 키 (기존 설정 재사용)
OPENAI_API_KEY=sk-...
```

### 2. 설정 파일 확인 (app/config/features/enrichment.yaml)

기본 설정이 이미 작성되어 있습니다. 필요 시 수정하세요.

```yaml
enrichment:
  enabled: false  # 기본값: 비활성화
  llm:
    model: gpt-4o-mini
    temperature: 0.1
    max_tokens: 1000
  batch:
    size: 10
    concurrency: 3
  timeout:
    single: 30
    batch: 90
```

---

## 사용 방법

### 1. 기본 사용 (단일 문서)

```python
from app.modules.core.enrichment import EnrichmentService
from app.lib.config_loader import load_config

# 설정 로드
config = load_config()

# 서비스 초기화
enrichment_service = EnrichmentService(config)
await enrichment_service.initialize()

# 단일 문서 보강
document = {
    "content": "고객: 친구 초대 코드는 어디서 입력하나요?\n상담원: ..."
}

result = await enrichment_service.enrich(document)

if result:
    print(f"카테고리: {result.category_main}")
    print(f"키워드: {result.keywords}")
    print(f"요약: {result.summary}")

# 정리
await enrichment_service.cleanup()
```

### 2. 배치 처리

```python
# 여러 문서 동시 보강
documents = [
    {"content": "친구 초대 코드..."},
    {"content": "결제 오류..."},
    {"content": "회원 탈퇴..."}
]

results = await enrichment_service.enrich_batch(documents)

for i, result in enumerate(results):
    if result:
        print(f"문서 {i+1}: {result.category_main} - {result.summary}")
    else:
        print(f"문서 {i+1}: 보강 실패 (원본 사용)")
```

### 3. 문서 로더 통합 (자동 보강)

```python
# 문서 로딩 시 자동 보강 (향후 구현 예정)
from app.modules.core.documents.loaders import DocumentLoaderFactory

loader = DocumentLoaderFactory.create_loader("example.json")
documents = await loader.load("example.json")

# 각 문서에 llm_enrichment 필드가 자동 추가됨
for doc in documents:
    enrichment = doc.metadata.get('llm_enrichment')
    if enrichment:
        print(f"카테고리: {enrichment['category_main']}")
```

### 4. 통계 확인

```python
# 보강 통계 조회
stats = enrichment_service.get_stats()

print(f"총 보강 시도: {stats['total_enrichments']}")
print(f"성공: {stats['successful_enrichments']}")
print(f"실패: {stats['failed_enrichments']}")
print(f"성공률: {stats['success_rate']:.2f}%")
print(f"토큰 사용량: {stats['total_tokens_used']}")
```

---

## 테스트

### 단위 테스트

```bash
# 전체 테스트 실행
pytest tests/unit/test_enrichment.py -v

# 특정 테스트 실행
pytest tests/unit/test_enrichment.py::test_llm_enricher_single -v
```

### 통합 테스트

```bash
# 전체 파이프라인 테스트
pytest tests/integration/test_enrichment_pipeline.py -v
```

---

## 문제 해결

### Q1: 보강이 동작하지 않아요

**확인 사항:**
1. `.env`에서 `ENRICHMENT_ENABLED=true`로 설정했는지 확인
2. `OPENAI_API_KEY`가 올바르게 설정되었는지 확인
3. 로그에서 "Enrichment enabled" 메시지 확인

```bash
# 로그 확인
tail -f logs/app.log | grep -i enrichment
```

### Q2: LLM 호출이 너무 느려요

**해결 방법:**
1. 배치 크기 조정: `.env`에서 `ENRICHMENT_BATCH_SIZE=5`로 감소
2. 타임아웃 증가: `ENRICHMENT_TIMEOUT_SINGLE=60`
3. 동시 처리 수 증가: `ENRICHMENT_CONCURRENCY=5`

### Q3: 비용이 너무 많이 나와요

**해결 방법:**
1. 캐싱 활성화: `ENRICHMENT_CACHE_ENABLED=true`
2. 배치 크기 증가: `ENRICHMENT_BATCH_SIZE=10` (토큰 효율)
3. 온도 낮추기: `ENRICHMENT_LLM_TEMPERATURE=0.0` (일관성 향상)
4. 모델 변경: `gpt-4o-mini` (이미 최저가 모델)

### Q4: JSON 파싱 에러가 발생해요

**원인:**
LLM이 JSON 외에 추가 텍스트를 출력하는 경우

**해결 방법:**
- 프롬프트에 "JSON만 출력" 강조 (이미 적용됨)
- 마크다운 코드 블록 제거 로직 (이미 적용됨)
- 재시도 로직 활용 (이미 적용됨)

### Q5: 특정 문서만 보강 실패해요

**확인 방법:**
```python
# 실패한 문서 ID 확인
failed_ids = []
for i, result in enumerate(results):
    if result is None:
        failed_ids.append(documents[i].get('_id'))

print(f"실패한 문서 ID: {failed_ids}")
```

**해결 방법:**
- 해당 문서의 `content` 필드 확인
- 문서 길이가 너무 긴지 확인 (토큰 제한)
- 로그에서 구체적인 에러 메시지 확인

---

## 성능 지표

### 예상 성능

| 항목 | 값 |
|------|-----|
| 단건 처리 시간 | 2-5초 |
| 배치 처리 시간 (10개) | 5-10초 |
| 토큰 사용량 (단건) | 300-500 tokens |
| 토큰 사용량 (배치 10개) | 1500-2500 tokens |
| 성공률 | 95%+ |

### 비용 예측 (gpt-4o-mini)

- **Input**: $0.15 / 1M tokens
- **Output**: $0.60 / 1M tokens

**예시 계산:**
- 문서 1,000개 처리
- 평균 400 tokens/document
- 총 비용: 약 $0.30 (30센트)

---

## 라이센스

이 모듈은 프로젝트 전체 라이센스를 따릅니다.

---

## 기여

문제 발견 시 이슈 등록 또는 PR 제출 환영합니다!

---

**마지막 업데이트**: 2025-11-07
**작성자**: AI Assistant
**버전**: 1.0.0
