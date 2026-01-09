# 로그 메시지 표준 가이드라인

**버전**: 1.0
**작성일**: 2026-01-08
**목적**: RAG_Standard 프로젝트 전반의 일관되고 안전한 로그 메시지 작성 표준 정의

---

## 📋 목차
1. [로그 레벨별 용도](#로그-레벨별-용도)
2. [메시지 형식 표준](#메시지-형식-표준)
3. [Emoji 정책](#emoji-정책)
4. [보안 고려사항](#보안-고려사항)
5. [코드 예시](#코드-예시)

---

## 로그 레벨별 용도

### `logger.error` - 시스템 오류
**용도**: 시스템이 정상적으로 동작하지 못하는 상황, 즉각적인 복구 조치가 필요한 경우

**사용 시나리오**:
- 외부 서비스 연결 실패 (Weaviate, MongoDB, Redis 등)
- 필수 설정 값 누락 또는 잘못된 형식
- 예상치 못한 예외 발생
- 데이터 무결성 위반

**예시**:
```python
logger.error(
    "Weaviate 연결 실패",
    extra={
        "url": weaviate_url,
        "error": str(e),
        "error_type": type(e).__name__,
        "suggestion": "docker-compose.weaviate.yml 실행 상태를 확인하세요"
    }
)
```

---

### `logger.warning` - 잠재적 문제
**용도**: 시스템은 동작하지만 주의가 필요한 상황, 모니터링이 필요한 경우

**사용 시나리오**:
- 폴백 메커니즘 작동 (주 서비스 실패 → 대체 서비스 사용)
- 성능 임계값 초과 경고
- 비권장 사용 패턴 감지
- 캐시 미스율 증가

**예시**:
```python
logger.warning(
    "Gemini 리랭커 실패로 폴백 사용",
    extra={
        "primary_reranker": "gemini",
        "fallback_reranker": "colbert",
        "error": str(e)
    }
)
```

---

### `logger.info` - 주요 이벤트
**용도**: 시스템의 정상적인 주요 이벤트, 비즈니스 로직 진행 상황 추적

**사용 시나리오**:
- API 요청/응답 성공
- RAG 파이프라인 단계 완료
- 설정 로드 성공
- 주요 초기화 완료

**예시**:
```python
logger.info(
    "RAG 파이프라인 검색 완료",
    extra={
        "document_count": len(documents),
        "query": query,
        "execution_time_ms": elapsed_ms,
        "retrieval_method": "hybrid"
    }
)
```

---

### `logger.debug` - 디버깅 정보
**용도**: 개발 환경에서의 상세한 추적 정보, 프로덕션에서는 비활성화

**사용 시나리오**:
- 함수 호출 매개변수
- 중간 계산 결과
- 상태 변화 추적
- 성능 프로파일링

**예시**:
```python
logger.debug(
    "임베딩 벡터 생성 완료",
    extra={
        "text_length": len(text),
        "vector_dimension": len(vector),
        "model": "text-embedding-004"
    }
)
```

---

## 메시지 형식 표준

### ✅ 권장 패턴: 명확한 한글 메시지 + 구조화된 컨텍스트

```python
logger.error(
    "Weaviate 연결 실패",  # 간결한 한글 메시지
    extra={                 # 구조화된 컨텍스트
        "url": weaviate_url,
        "error": str(e),
        "error_type": type(e).__name__,
        "suggestion": "docker-compose.weaviate.yml 실행 상태를 확인하세요"
    }
)
```

**장점**:
- 로그 파싱 도구와 호환성 우수
- 민감 정보 노출 방지 (extra는 자동 필터링 가능)
- 구조화된 분석 가능 (JSON 변환 용이)
- 다국어 지원 용이 (메시지만 번역)

---

### ❌ 지양 패턴 1: Emoji 혼용

```python
# ❌ 나쁜 예
logger.error(f"⚠️ RAG 검색 실패: {rag_result}")
logger.error("🚨 프롬프트 누출 감지")

# ✅ 좋은 예
logger.error("RAG 검색 실패", extra={"result": rag_result})
logger.error("프롬프트 누출 감지", extra={"answer_preview": answer[:100]})
```

**문제점**:
- 로그 파싱 도구 호환성 저하
- 터미널 인코딩 문제 발생 가능
- 검색 및 필터링 어려움

---

### ❌ 지양 패턴 2: F-string에 민감 정보 포함

```python
# ❌ 나쁜 예
logger.error(f"MongoDB 연결 실패: {mongodb_uri}")  # URI에 패스워드 포함 가능

# ✅ 좋은 예
logger.error(
    "MongoDB 연결 실패",
    extra={
        "host": parsed_uri.hostname,
        "database": parsed_uri.database,
        "error": str(e)
        # 패스워드는 제외
    }
)
```

**문제점**:
- 민감 정보 (API 키, 패스워드, 개인정보) 로그 노출
- GDPR, 개인정보보호법 위반 위험
- 보안 감사 실패

---

### ❌ 지양 패턴 3: 비구조화된 메시지

```python
# ❌ 나쁜 예
logger.info(f"검색 완료: {len(results)}개 문서, 실행시간 {elapsed_ms}ms")

# ✅ 좋은 예
logger.info(
    "검색 완료",
    extra={
        "document_count": len(results),
        "execution_time_ms": elapsed_ms,
        "query": query
    }
)
```

**문제점**:
- 로그 분석 도구로 메트릭 추출 어려움
- 시계열 분석 불가능
- 알림 조건 설정 복잡

---

## Emoji 정책

### 원칙
- **로그 메시지**: Emoji 사용 금지 (100%)
- **사용자 응답 메시지**: Emoji 선택적 사용 허용

### 이유
1. **로그 파싱 도구 호환성**: Elasticsearch, Splunk 등은 ASCII 기반 검색 최적화
2. **터미널 인코딩**: 일부 환경에서 깨짐 현상 발생
3. **검색 및 필터링**: 정확한 에러 검색 어려움
4. **국제화**: Emoji 의미가 문화권별로 다를 수 있음

### 마이그레이션 가이드

```python
# Before (Emoji 사용)
logger.error("⚠️ 연결 실패")
logger.warning("🔄 재시도 중")
logger.info("✅ 완료")

# After (텍스트만 사용)
logger.error("연결 실패")
logger.warning("재시도 중", extra={"attempt": retry_count})
logger.info("완료", extra={"status": "success"})
```

---

## 보안 고려사항

### 1. 민감 정보 로그 노출 방지

**민감 정보 카테고리**:
- API 키, 액세스 토큰
- 데이터베이스 연결 문자열 (패스워드 포함)
- 개인정보 (이름, 이메일, 전화번호)
- 세션 ID, JWT 토큰
- 신용카드 정보

**안전한 로깅 패턴**:
```python
# ❌ 위험: API 키 노출
logger.debug(f"API 요청: {url}?api_key={api_key}")

# ✅ 안전: 마스킹 처리
logger.debug(
    "API 요청",
    extra={
        "url": url,
        "api_key_preview": f"{api_key[:8]}...{api_key[-4:]}" if api_key else None
    }
)

# ❌ 위험: 전체 URI 노출 (패스워드 포함)
logger.error(f"MongoDB 연결 실패: {mongodb_uri}")

# ✅ 안전: 호스트와 DB만 로깅
from urllib.parse import urlparse
parsed = urlparse(mongodb_uri)
logger.error(
    "MongoDB 연결 실패",
    extra={
        "host": parsed.hostname,
        "database": parsed.path.lstrip('/'),
        "error": str(e)
    }
)
```

---

### 2. F-string 대신 Extra 사용

**이유**:
- Extra는 로그 필터링 시스템에서 자동 마스킹 가능
- F-string은 메시지에 직접 삽입되어 필터링 어려움
- 구조화된 로그 분석 가능

```python
# ❌ 필터링 불가능
logger.error(f"검색 실패: 사용자 {user_email}")

# ✅ 필터링 가능
logger.error(
    "검색 실패",
    extra={
        "user_email": user_email  # 자동 필터링 시스템에서 마스킹 가능
    }
)
```

---

## 코드 예시

### 예시 1: 외부 서비스 연결 실패

```python
def connect_to_weaviate(url: str, api_key: str | None) -> WeaviateClient:
    """Weaviate 클라이언트 연결"""
    try:
        client = WeaviateClient(
            url=url,
            auth_client_secret=AuthApiKey(api_key) if api_key else None
        )
        logger.info(
            "Weaviate 연결 성공",
            extra={
                "url": url,
                "auth_enabled": api_key is not None
            }
        )
        return client
    except Exception as e:
        logger.error(
            "Weaviate 연결 실패",
            extra={
                "url": url,
                "error": str(e),
                "error_type": type(e).__name__,
                "suggestion": (
                    "1. docker-compose.weaviate.yml이 실행 중인지 확인하세요 (docker ps)\n"
                    "2. WEAVIATE_URL 환경 변수가 올바른지 확인하세요\n"
                    "3. 네트워크 연결 상태를 확인하세요"
                )
            }
        )
        raise
```

---

### 예시 2: RAG 파이프라인 실행

```python
async def execute_rag_pipeline(query: str) -> dict:
    """RAG 파이프라인 실행"""
    start_time = time.time()

    try:
        # 검색 단계
        documents = await retriever.retrieve(query)
        logger.info(
            "문서 검색 완료",
            extra={
                "query": query,
                "document_count": len(documents),
                "stage": "retrieval"
            }
        )

        # 리랭킹 단계
        reranked_docs = await reranker.rerank(query, documents)
        logger.info(
            "리랭킹 완료",
            extra={
                "input_count": len(documents),
                "output_count": len(reranked_docs),
                "stage": "reranking"
            }
        )

        # 답변 생성 단계
        answer = await generator.generate(query, reranked_docs)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "RAG 파이프라인 완료",
            extra={
                "query": query,
                "execution_time_ms": elapsed_ms,
                "final_document_count": len(reranked_docs),
                "status": "success"
            }
        )

        return {"answer": answer, "sources": reranked_docs}

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "RAG 파이프라인 실패",
            extra={
                "query": query,
                "execution_time_ms": elapsed_ms,
                "error": str(e),
                "error_type": type(e).__name__,
                "status": "failed"
            }
        )
        raise
```

---

### 예시 3: 설정 로드 실패

```python
def load_config(config_path: str) -> dict:
    """YAML 설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        logger.info(
            "설정 파일 로드 성공",
            extra={
                "config_path": config_path,
                "keys": list(config.keys())
            }
        )
        return config

    except FileNotFoundError:
        logger.error(
            "설정 파일을 찾을 수 없음",
            extra={
                "config_path": config_path,
                "current_directory": os.getcwd(),
                "suggestion": "설정 파일 경로가 올바른지 확인하세요. 예시: app/config/base.yaml"
            }
        )
        raise

    except yaml.YAMLError as e:
        logger.error(
            "설정 파일 파싱 실패",
            extra={
                "config_path": config_path,
                "error": str(e),
                "suggestion": "YAML 형식이 올바른지 확인하세요. 온라인 YAML 검증기를 사용하세요."
            }
        )
        raise
```

---

### 예시 4: API 키 누락

```python
def get_google_api_key() -> str:
    """Google API 키 가져오기"""
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logger.error(
            "GOOGLE_API_KEY 환경 변수 누락",
            extra={
                "env_file": ".env",
                "suggestion": (
                    "1. .env 파일에 'GOOGLE_API_KEY=AIza...'를 추가하세요\n"
                    "2. API 키 발급: https://makersuite.google.com/app/apikey\n"
                    "3. .env.example 파일을 참고하세요"
                )
            }
        )
        raise ValueError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다")

    logger.debug(
        "API 키 로드 완료",
        extra={
            "key_preview": f"{api_key[:8]}...{api_key[-4:]}"
        }
    )
    return api_key
```

---

## 체크리스트

로그 메시지 작성 시 다음을 확인하세요:

- [ ] 적절한 로그 레벨 사용 (error/warning/info/debug)
- [ ] Emoji 미사용
- [ ] F-string 대신 extra 사용
- [ ] 민감 정보 노출 확인 (API 키, 패스워드, 개인정보)
- [ ] 구조화된 컨텍스트 제공 (extra 딕셔너리)
- [ ] 에러 발생 시 해결 방법 제시 (suggestion 필드)
- [ ] 일관된 필드명 사용 (error, error_type, suggestion 등)

---

**참고 문서**:
- [에러 메시지 표준](./error_message_standards.md)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Structured Logging](https://www.structlog.org/)
