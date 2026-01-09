# Phase 2: 에러 및 로그 관리 통합 개선 계획

## 📋 개요

**목표**: 안전하고 일관된 에러 처리 및 로그 시스템 구축
**예상 시간**: 90분 (3개 작업 통합)
**리스크**: 낮음 (문자열 및 문서 수정 중심)

## 🎯 작업 범위

### Task 4: .env.example 문서화 강화
- **시간**: 20분
- **리스크**: 없음
- **영향**: 1개 파일 (.env.example)

### Task 5: 에러 메시지 개선
- **시간**: 30분
- **리스크**: 낮음
- **영향**: 약 15-20개 파일 (주요 에러 처리 지점)

### Task 6: 로그 메시지 통일
- **시간**: 40분
- **리스크**: 낮음
- **영향**: 약 20-30개 파일 (핵심 로그 지점)

---

## 📐 현재 상태 분석

### 문제점

#### 1. 로그 메시지 불일치
```python
# 패턴 A: emoji + f-string
logger.error(f"⚠️ RAG 검색 실패: {rag_result}")

# 패턴 B: 한글 + extra
logger.error("Weaviate 연결 실패", extra={"error": str(e)})

# 패턴 C: emoji + 한글
logger.error("🚨 프롬프트 누출 감지 - 답변 차단")
```

#### 2. 에러 메시지 정보 부족
```python
# 현재: 문제만 알림
logger.error("MongoDB 연결 실패")

# 개선 필요: 해결 방법 제시
logger.error("MongoDB 연결 실패. MONGODB_URI 환경 변수를 확인하세요.")
```

#### 3. .env.example 설명 부족
```bash
# 현재: 변수명만
WEAVIATE_URL=https://your-weaviate-instance.example.com

# 개선 필요: 목적, 기본값, 필수 여부
# Weaviate 벡터 DB URL (필수)
# - 로컬: http://localhost:8080
# - 프로덕션: https://로 시작 (보안 검증)
WEAVIATE_URL=http://localhost:8080
```

---

## 🏗️ 통합 실행 계획

### Phase 1: 표준 가이드라인 정의 (10분)

#### 1.1 로그 메시지 표준
**위치**: `docs/standards/logging_standards.md` (신규 생성)

**레벨별 용도**:
- `logger.error`: 시스템 오류 (복구 필요)
- `logger.warning`: 잠재적 문제 (모니터링 필요)
- `logger.info`: 주요 이벤트 (정상 동작)
- `logger.debug`: 디버깅 정보 (개발 환경)

**메시지 형식**:
```python
# ✅ 권장: 명확한 한글 메시지 + 구조화된 컨텍스트
logger.error(
    "Weaviate 연결 실패",
    extra={
        "url": weaviate_url,
        "error": str(e),
        "error_type": type(e).__name__,
        "suggestion": "docker-compose.weaviate.yml 실행 상태를 확인하세요"
    }
)

# ❌ 지양: emoji 혼용, f-string에 민감 정보 포함
logger.error(f"⚠️ 연결 실패: {sensitive_data}")
```

**Emoji 정책**:
- 로그 메시지에 emoji 사용 금지 (로그 파싱 도구 호환성)
- 사용자 응답 메시지에만 선택적 사용 허용

#### 1.2 에러 메시지 표준
**위치**: `docs/standards/error_message_standards.md` (신규 생성)

**구조**:
```
[문제 설명] + [원인 추정] + [해결 방법]
```

**예시**:
```python
# ✅ 권장
error_message = (
    "Weaviate 연결 실패. "
    "네트워크 오류 또는 Weaviate 서버 미실행 상태입니다. "
    "docker-compose.weaviate.yml이 실행 중인지 확인하세요."
)

# ❌ 지양
error_message = "Weaviate 연결 실패"
```

---

### Phase 2: .env.example 문서화 강화 (20분)

#### 2.1 작업 범위
**파일**: `.env.example`

#### 2.2 개선 항목

**각 변수에 추가할 정보**:
1. **목적**: 변수의 역할 설명
2. **필수/선택**: 시스템 동작에 필수인지 여부
3. **기본값**: 권장 기본값 (있는 경우)
4. **예시**: 실제 사용 예시
5. **유효 범위**: 허용되는 값의 범위
6. **연관 설정**: 관련된 다른 환경 변수

**템플릿**:
```bash
# ============================================================
# [카테고리명]
# ============================================================

# [변수명] - [목적]
# 필수: [예/아니오]
# 기본값: [값 또는 "없음"]
# 예시: [실제 예시]
# 유효 범위: [범위 설명]
# 연관 설정: [관련 변수들]
[변수명]=[기본값 또는 예시값]
```

**우선순위 변수**:
1. `FASTAPI_AUTH_KEY` - 보안 핵심
2. `GOOGLE_API_KEY` - LLM 핵심
3. `WEAVIATE_URL` - 벡터 DB 핵심
4. `MONGODB_URI` - 세션 저장소
5. `ENVIRONMENT` - 환경 감지 (v3.3.1 추가)
6. `LANGFUSE_*` - 관찰성

#### 2.3 구현 전략
- **기존 구조 유지**: 카테고리 분류 보존
- **점진적 개선**: 필수 변수 먼저, 선택 변수 나중
- **검증**: 실제 `.env` 파일과 호환성 확인

---

### Phase 3: 에러 메시지 개선 (30분)

#### 3.1 우선순위 파일 (15개)
**Tier 1: 인프라 연결 (가장 빈번한 에러)**
1. `app/lib/weaviate_client.py` - Weaviate 연결
2. `app/lib/mongodb_client.py` - MongoDB 연결
3. `app/lib/config_loader.py` - 설정 로드
4. `app/lib/environment.py` - 환경 감지
5. `app/lib/auth.py` - 인증 실패

**Tier 2: 핵심 비즈니스 로직**
6. `app/api/services/rag_pipeline.py` - RAG 파이프라인
7. `app/modules/core/retrieval/orchestrator.py` - 검색 오케스트레이션
8. `app/modules/core/generation/generator.py` - 답변 생성
9. `app/modules/core/agent/executor.py` - Agent 실행

**Tier 3: 지원 모듈**
10. `app/core/di_container.py` - DI 컨테이너
11. `app/modules/core/graph/factory.py` - GraphRAG 팩토리
12. `app/modules/core/embedding/factory.py` - 임베더 팩토리
13. `app/modules/core/retrieval/cache/factory.py` - 캐시 팩토리
14. `main.py` - 앱 시작

#### 3.2 개선 패턴

**패턴 A: 연결 실패**
```python
# Before
logger.error("Weaviate 연결 실패", extra={"error": str(e)})

# After
logger.error(
    "Weaviate 연결 실패",
    extra={
        "error": str(e),
        "error_type": type(e).__name__,
        "url": self._config.get("url"),
        "suggestion": (
            "1. docker-compose.weaviate.yml이 실행 중인지 확인하세요 (docker ps)\n"
            "2. WEAVIATE_URL 환경 변수가 올바른지 확인하세요\n"
            "3. 네트워크 연결 상태를 확인하세요"
        )
    }
)
```

**패턴 B: 설정 오류**
```python
# Before
raise ConfigError("설정 파일 로드 실패")

# After
raise ConfigError(
    f"설정 파일 로드 실패: {config_path}. "
    f"파일이 존재하는지 확인하고, YAML 형식이 올바른지 검증하세요. "
    f"예시: app/config/base.yaml"
)
```

**패턴 C: API 키 누락**
```python
# Before
raise ValueError("API 키가 없습니다")

# After
raise ValueError(
    "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
    ".env 파일에 'GOOGLE_API_KEY=AIza...'를 추가하세요. "
    "발급 방법: https://makersuite.google.com/app/apikey"
)
```

#### 3.3 구현 체크리스트
- [ ] Tier 1 파일 개선 (10분)
- [ ] Tier 2 파일 개선 (10분)
- [ ] Tier 3 파일 개선 (10분)
- [ ] 테스트 실행으로 에러 메시지 검증

---

### Phase 4: 로그 메시지 통일 (40분)

#### 4.1 우선순위 파일 (20개)
**핵심 모듈 (Tier 1)**
1. `app/api/services/rag_pipeline.py`
2. `app/modules/core/retrieval/orchestrator.py`
3. `app/modules/core/generation/generator.py`
4. `app/lib/weaviate_client.py`
5. `app/lib/mongodb_client.py`

**지원 모듈 (Tier 2)**
6. `app/modules/core/agent/executor.py`
7. `app/modules/core/agent/orchestrator.py`
8. `app/modules/core/graph/builder.py`
9. `app/modules/core/privacy/processor.py`
10. `app/modules/core/session/facade.py`

**인프라 (Tier 3)**
11. `app/core/di_container.py`
12. `main.py`
13. `app/api/routers/chat_router.py`
14. `app/api/routers/admin_router.py`
15. `app/middleware/error_logger.py`

#### 4.2 통일 규칙

**1. Emoji 제거**
```python
# Before
logger.error(f"⚠️ RAG 검색 실패: {rag_result}")
logger.error("🚨 프롬프트 누출 감지")

# After
logger.error("RAG 검색 실패", extra={"result": rag_result})
logger.error("프롬프트 누출 감지", extra={"answer_preview": answer[:100]})
```

**2. F-string 제거 (민감 정보 보호)**
```python
# Before
logger.error(f"검색 실패: {e}")

# After
logger.error(
    "검색 실패",
    extra={
        "error": str(e),
        "error_type": type(e).__name__
    }
)
```

**3. 구조화된 컨텍스트**
```python
# Before
logger.info(f"검색 완료: {len(results)}개 문서")

# After
logger.info(
    "검색 완료",
    extra={
        "document_count": len(results),
        "query": query,
        "execution_time_ms": elapsed_ms
    }
)
```

**4. 일관된 메시지 형식**
```python
# 성공 케이스
logger.info("[모듈명] 작업 완료", extra={...})

# 경고 케이스
logger.warning("[모듈명] 잠재적 문제 감지", extra={...})

# 에러 케이스
logger.error("[모듈명] 작업 실패", extra={...})
```

#### 4.3 구현 전략
1. **자동화 가능한 부분**: emoji 제거 (정규식 사용)
2. **수동 검토 필요**: 민감 정보 포함 여부
3. **점진적 적용**: Tier별 순차 진행

---

### Phase 5: 검증 및 문서화 (10분)

#### 5.1 검증 체크리스트
```bash
# 1. 테스트 통과 확인
make test

# 2. 타입 체크 통과 확인
make type-check

# 3. 린트 통과 확인
make lint

# 4. 로그 메시지 일관성 검증
grep -r "logger.error.*⚠️" app/  # emoji 남아있는지 확인
grep -r "logger.error.*f\"" app/  # f-string 직접 사용 확인

# 5. 에러 메시지 개선 확인
python -c "from app.lib.weaviate_client import WeaviateClient; WeaviateClient()" 2>&1 | grep "suggestion"
```

#### 5.2 문서 업데이트
1. `CHANGELOG.md` - Phase 2 내용 추가
2. `docs/standards/logging_standards.md` - 로그 표준 문서
3. `docs/standards/error_message_standards.md` - 에러 표준 문서
4. `CLAUDE.md` - 가이드라인 참조 추가

---

## 📊 예상 결과

### 정량적 개선
- `.env.example`: 주석 2배 증가 (80줄 → 160줄)
- 에러 메시지: 해결 방법 100% 포함 (0% → 100%)
- 로그 일관성: emoji 제거 100%, extra 사용 80%+

### 정성적 개선
- **개발자 경험**: 에러 발생 시 즉시 해결 방법 확인 가능
- **운영 효율성**: 로그 파싱 도구와 호환성 향상
- **보안**: 민감 정보 로그 노출 제거

---

## 🚨 리스크 관리

### 잠재적 리스크
1. **로그 메시지 변경으로 인한 모니터링 알림 오작동**
   - 완화: 로그 레벨 변경 없음, 메시지 형식만 개선

2. **에러 메시지 변경으로 인한 테스트 실패**
   - 완화: 테스트는 에러 타입만 검증, 메시지는 검증 안 함

3. **과도한 상세 정보로 인한 로그 볼륨 증가**
   - 완화: extra는 구조화된 데이터, 압축 효율 높음

### 롤백 계획
- Git 커밋 단위: Phase별 개별 커밋
- 문제 발생 시: `git revert` 로 Phase별 롤백 가능

---

## 📅 실행 타임라인

### 총 소요 시간: 90분

| Phase | 작업 | 시간 | 누적 |
|-------|------|------|------|
| Phase 1 | 표준 가이드라인 정의 | 10분 | 10분 |
| Phase 2 | .env.example 강화 | 20분 | 30분 |
| Phase 3 | 에러 메시지 개선 (Tier 1-3) | 30분 | 60분 |
| Phase 4 | 로그 메시지 통일 (Tier 1-3) | 40분 | 100분 |
| Phase 5 | 검증 및 문서화 | 10분 | 110분 |
| **버퍼** | 예상치 못한 이슈 대응 | - | - |

### 권장 실행 순서
1. **Phase 1 + Phase 2**: 독립적, 병렬 가능 (30분)
2. **Phase 3 + Phase 4**: 순차 권장 (에러→로그 순서) (70분)
3. **Phase 5**: 전체 검증 (10분)

---

## ✅ 완료 기준

### Task 4: .env.example
- [ ] 모든 필수 변수에 5가지 정보 포함 (목적/필수여부/기본값/예시/유효범위)
- [ ] 카테고리별 변수 그룹화 유지
- [ ] 실제 `.env` 파일과 호환성 확인

### Task 5: 에러 메시지
- [ ] Tier 1-3 모든 파일에 해결 방법 포함
- [ ] 에러 메시지 구조: [문제] + [원인] + [해결]
- [ ] 테스트 통과 (1,117개)

### Task 6: 로그 메시지
- [ ] Tier 1-3 모든 파일에서 emoji 제거
- [ ] logger.error/warning 80%+ extra 사용
- [ ] 민감 정보 f-string 직접 노출 0건
- [ ] 테스트 통과 (1,117개)

---

## 🎯 성공 지표

### 즉시 측정 가능
- Emoji 사용: 현재 ~30개 → 목표 0개
- Extra 사용률: 현재 ~50% → 목표 80%+
- 해결 방법 포함률: 현재 0% → 목표 100%

### 장기 측정 가능
- 에러 해결 시간: 개발자 피드백 수집
- 운영 문의 감소: 에러 메시지 개선 효과
- 로그 분석 효율: 구조화된 로그 활용도

---

**작성자**: Claude Opus 4.5
**작성일**: 2026-01-08
**버전**: 1.0
