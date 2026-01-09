# Infrastructure QA 분석 보고서

**분석자**: Infrastructure QA 전문가
**분석 일자**: 2026-01-08
**프로젝트**: RAG_Standard v3.3.0
**대상**: PostgreSQL, MongoDB, Weaviate 인프라 연결 관리

---

## 📋 Executive Summary

RAG_Standard 프로젝트의 인프라스트럭처 연결 관리를 분석한 결과, **전반적으로 우수한 설계**를 보유하고 있으나 **몇 가지 개선이 필요한 영역**이 발견되었습니다.

**종합 평가**: ⚠️ **B+ (양호, 개선 필요)**

### 주요 발견 사항
- ✅ **강점**: Connection Pooling, Graceful Shutdown, 싱글톤 패턴
- ⚠️ **개선 필요**: Timeout 일관성, Connection Leak 감지, Health Check

---

## 1. PostgreSQL 연결 관리 검증

### 📁 분석 대상
- `app/infrastructure/persistence/connection.py` (DatabaseManager)
- `app/infrastructure/storage/metadata/postgres_store.py` (PostgresMetadataStore)

### ✅ 강점

#### 1.1 Connection Pooling 구성
```python
# connection.py:118-124
self.engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,      # ✅ 연결 재사용 전 Health Check
    pool_size=5,             # ✅ 최소 5개 연결 유지
    max_overflow=10,         # ✅ 최대 15개 연결 허용 (5+10)
)
```

**평가**:
- `pool_pre_ping=True`로 stale connection 방지
- 적절한 pool size (5개 기본, 최대 15개)
- Railway PostgreSQL 기본 스펙(100 connections)에 여유 있음

#### 1.2 Context Manager 패턴
```python
# connection.py:167-188
@asynccontextmanager
async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
    async with self.async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()  # ✅ 에러 시 자동 롤백
            raise
        finally:
            await session.close()     # ✅ 항상 세션 종료
```

**평가**:
- Try-Except-Finally 패턴으로 리소스 누수 방지
- 트랜잭션 자동 커밋/롤백

#### 1.3 Graceful Shutdown
```python
# connection.py:160-165
async def close(self) -> None:
    if self.engine:
        await self.engine.dispose()  # ✅ 모든 연결 정리
        self._initialized = False
        logger.info("데이터베이스 연결 종료")
```

**평가**: 명시적 engine dispose로 안전한 종료

### ⚠️ 개선 필요 사항

#### 1.4 Timeout 설정 누락
**문제점**:
```python
# connection.py:118 - Timeout 설정 없음
self.engine = create_async_engine(
    database_url,
    # ❌ connect_timeout 미설정
    # ❌ pool_timeout 미설정
    # ❌ pool_recycle 미설정
)
```

**영향**:
- 데드락 시 무한 대기 가능
- 장시간 유휴 연결 재활용 없음
- 연결 획득 대기 시간 제한 없음

**권장 사항**:
```python
self.engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    # 추가 권장 설정
    connect_args={"timeout": 10},        # 연결 timeout 10초
    pool_timeout=30,                     # pool 대기 timeout 30초
    pool_recycle=3600,                   # 1시간마다 연결 재활용
)
```

#### 1.5 PostgresMetadataStore의 SQL Injection 검증 미흡
**문제점**:
```python
# postgres_store.py:29-32
def _validate_collection_name(self, collection: str) -> None:
    if not re.match(r'^[a-zA-Z0-9_]+$', collection):
        raise ValueError(f"Invalid collection name: {collection}")
```

**영향**:
- 테이블 이름 검증은 있으나 WHERE 절의 컬럼명 검증 없음
- SQL Injection 가능성 낮으나 완벽하지 않음

**권장 사항**:
- WHERE 절 컬럼명도 화이트리스트 검증
- SQLAlchemy ORM 사용 고려 (현재 Raw Query)

---

## 2. MongoDB 연결 관리 검증

### 📁 분석 대상
- `app/lib/mongodb_client.py` (MongoDBClient)

### ✅ 강점

#### 2.1 Connection Pooling 구성
```python
# mongodb_client.py:75-81
connection_options = {
    "maxPoolSize": self._config.get("max_pool_size", 10),    # ✅ 최대 10개
    "minPoolSize": self._config.get("min_pool_size", 1),     # ✅ 최소 1개
    "retryWrites": self._config.get("retry_writes", True),   # ✅ 재시도 활성화
    "w": self._config.get("w", "majority"),                  # ✅ Write Concern
    "serverSelectionTimeoutMS": int(self._config.get("timeout_ms", 5000)),  # ✅ 5초 타임아웃
}
```

**평가**:
- pymongo 기본 권장 설정 준수
- Atlas 클라우드 환경에 적합한 timeout 설정 (5초)
- Write Concern "majority"로 데이터 안정성 확보

#### 2.2 싱글톤 패턴
```python
# mongodb_client.py:53-57
def __new__(cls) -> "MongoDBClient":
    if cls._instance is None:
        cls._instance = super().__new__(cls)
    return cls._instance
```

**평가**: 애플리케이션 전체에서 단일 연결 인스턴스 공유

#### 2.3 에러 핸들링
```python
# mongodb_client.py:102-126
except ConnectionFailure as e:
    logger.error("MongoDB 연결 실패 - 네트워크 또는 인증 문제")
except ServerSelectionTimeoutError as e:
    logger.error("MongoDB 서버 선택 타임아웃")
except ConfigurationError as e:
    logger.error("MongoDB 설정 오류")
```

**평가**: pymongo 예외별 명확한 에러 처리

### ⚠️ 개선 필요 사항

#### 2.4 Connection Leak 감지 없음
**문제점**:
```python
# mongodb_client.py:84
self._client = MongoClient(self._config["uri"], **connection_options)
```

**영향**:
- 연결 누수 발생 시 모니터링 불가
- maxPoolSize 도달 여부 확인 불가

**권장 사항**:
```python
# 주기적 연결 풀 상태 모니터링
def get_pool_stats(self) -> dict:
    if self._client:
        server_info = self._client.server_info()
        return {
            "pool_size": len(self._client._MongoClient__all_credentials),
            "active_connections": self._client._topology._server_sessions.pool.active_count,
        }
    return {}
```

#### 2.5 Close 시 연결 상태 검증 없음
**문제점**:
```python
# mongodb_client.py:218-222
def close(self) -> None:
    if self._client is not None:
        self._client.close()  # ❌ 강제 종료, 진행 중인 작업 확인 없음
        self._client = None
```

**영향**:
- 진행 중인 쿼리 중단 가능
- Graceful Shutdown 미흡

**권장 사항**:
```python
def close(self, force: bool = False) -> None:
    if self._client is not None:
        if not force:
            # 진행 중인 작업 대기 (timeout 5초)
            time.sleep(5)
        self._client.close()
        self._client = None
```

---

## 3. Weaviate 연결 관리 검증

### 📁 분석 대상
- `app/lib/weaviate_client.py` (WeaviateClient)
- `app/infrastructure/storage/vector/weaviate_store.py` (WeaviateVectorStore)

### ✅ 강점

#### 3.1 로컬/프로덕션 분기 처리
```python
# weaviate_client.py:77-98
if url.startswith("http://localhost"):
    self._client = weaviate.connect_to_local(...)  # ✅ 로컬 전용 함수
else:
    connection_params = ConnectionParams.from_url(url, grpc_port)
    self._client = weaviate.WeaviateClient(
        connection_params=connection_params,
        skip_init_checks=True,  # ✅ Railway 환경 대응
    )
```

**평가**: Railway 환경의 gRPC health check 문제 우회

#### 3.2 Health Check
```python
# weaviate_client.py:174-187
def is_ready(self) -> bool:
    if self._client is None:
        return False
    try:
        return bool(self._client.is_ready())
    except Exception as e:
        logger.error("Weaviate ready check 실패")
        return False
```

**평가**: 연결 상태 확인 API 제공

#### 3.3 Cleanup 구현
```python
# weaviate_store.py:123-129
def close(self) -> None:
    if hasattr(self, "client") and self.client:
        self.client.close()

def __del__(self) -> None:
    self.close()
```

**평가**: `__del__` 매직 메서드로 자동 정리 보장

### ⚠️ 개선 필요 사항

#### 3.4 Timeout 일관성 부족
**문제점**:
```python
# weaviate_client.py:74
timeout = self._config.get("timeout", 30)  # ❌ 변수만 선언, 실제 미사용
```

**영향**:
- 설정 파일의 timeout 값이 실제 연결에 적용되지 않음
- Weaviate SDK 기본값(30초) 사용

**권장 사항**:
```python
# connection_params에 timeout 전달
connection_params = ConnectionParams.from_url(
    url,
    grpc_port,
    timeout_config=weaviate.TimeoutConfig(query=timeout)
)
```

#### 3.5 연결 재시도 로직 없음
**문제점**:
```python
# weaviate_client.py:98
self._client.connect()  # ❌ 1회 시도, 실패 시 포기
```

**영향**:
- 일시적 네트워크 장애 시 복구 불가
- Railway 배포 초기 연결 실패 가능

**권장 사항**:
```python
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10)
)
def _connect_with_retry(self):
    self._client.connect()
```

---

## 4. Connection Pooling 종합 평가

### 4.1 PostgreSQL (SQLAlchemy)
| 항목 | 설정값 | 평가 |
|------|--------|------|
| Pool Size | 5 | ✅ 적절 |
| Max Overflow | 10 | ✅ 적절 |
| Pool Pre-Ping | True | ✅ 우수 |
| Timeout | ❌ 없음 | ⚠️ 개선 필요 |
| Pool Recycle | ❌ 없음 | ⚠️ 개선 필요 |

### 4.2 MongoDB (pymongo)
| 항목 | 설정값 | 평가 |
|------|--------|------|
| Max Pool Size | 10 | ✅ 적절 |
| Min Pool Size | 1 | ✅ 적절 |
| Server Selection Timeout | 5000ms | ✅ 적절 |
| Retry Writes | True | ✅ 우수 |
| 모니터링 | ❌ 없음 | ⚠️ 개선 필요 |

### 4.3 Weaviate (weaviate-client)
| 항목 | 설정값 | 평가 |
|------|--------|------|
| Connection Type | HTTP + gRPC | ✅ 우수 |
| Timeout | 설정 미적용 | ⚠️ 개선 필요 |
| Retry Logic | ❌ 없음 | ⚠️ 개선 필요 |
| Health Check | is_ready() | ✅ 우수 |

---

## 5. 리소스 정리 (Cleanup) 검증

### 5.1 Graceful Shutdown 구현 현황

#### main.py Lifespan
```python
# main.py:342-393
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 시작 시
    yield
    # 종료 시
    try:
        await rag_app.cleanup_modules()          # ✅ DI Container cleanup
        await db_manager.close()                 # ✅ PostgreSQL
        weaviate_client.close()                  # ✅ Weaviate
        mongodb_client.close()                   # ✅ MongoDB
    except Exception as e:
        logger.warning(f"⚠️ Cleanup warning: {e}")  # ✅ 에러 무시하고 계속
```

**평가**: ✅ **우수한 Graceful Shutdown 구현**
- Try-Except로 일부 실패해도 전체 종료 보장
- 의존성 역순으로 정리 (Application → DB)

#### DI Container Cleanup
```python
# di_container.py:1702-1803
async def cleanup_resources(container: AppContainer) -> None:
    cleanup_errors: list[str] = []

    # 1. Session Manager
    # 2. Document Processor
    # 3. Graph Store
    # 4. Retrieval Orchestrator
    # 5. Vector Store
    # 6. Metadata Store
    # 7. Generation Module

    if cleanup_errors:
        logger.warning(f"⚠️ Cleanup completed with {len(cleanup_errors)} error(s)")
```

**평가**: ✅ **체계적인 정리 순서**
- 의존성 역순 정리
- 에러 수집 후 일괄 로깅

### ⚠️ 개선 필요 사항

#### 5.2 Timeout 미설정
**문제점**:
```python
# di_container.py:1760
await retrieval.close()  # ❌ 무한 대기 가능
```

**영향**:
- Cleanup 중 hang 발생 가능
- Kubernetes 등에서 강제 종료될 수 있음

**권장 사항**:
```python
import asyncio

async def cleanup_with_timeout(coro, timeout=10):
    try:
        await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Cleanup timeout after {timeout}s")

# 사용
await cleanup_with_timeout(retrieval.close())
```

#### 5.3 Connection Leak 감지 없음
**문제점**:
- 종료 시 활성 연결 수 확인 없음
- 누수 발생 여부 모니터링 불가

**권장 사항**:
```python
async def close(self) -> None:
    # 종료 전 연결 풀 상태 로깅
    if self.engine:
        pool = self.engine.pool
        logger.info(f"PostgreSQL Pool: size={pool.size()}, checked_in={pool.checkedin()}")
        await self.engine.dispose()
```

---

## 6. 타임아웃 처리 분석

### 6.1 현재 Timeout 설정 현황

| 컴포넌트 | Timeout 설정 | 기본값 | 평가 |
|----------|-------------|--------|------|
| PostgreSQL Connect | ❌ 없음 | 무제한 | ⚠️ 위험 |
| PostgreSQL Pool Acquire | ❌ 없음 | 무제한 | ⚠️ 위험 |
| MongoDB Server Selection | ✅ 5000ms | 30000ms | ✅ 우수 |
| Weaviate Connection | ❌ 미적용 | 30000ms | ⚠️ 개선 필요 |
| DI Cleanup | ❌ 없음 | 무제한 | ⚠️ 위험 |

### 6.2 권장 Timeout 값

```yaml
# config.yaml (권장)
infrastructure:
  postgres:
    connect_timeout: 10        # 연결 타임아웃 10초
    pool_timeout: 30           # Pool 획득 타임아웃 30초
    query_timeout: 60          # 쿼리 타임아웃 60초
    pool_recycle: 3600         # 1시간마다 연결 재활용

  mongodb:
    serverSelectionTimeoutMS: 5000   # ✅ 현재 설정 유지
    socketTimeoutMS: 20000           # Socket 타임아웃 20초 (추가 권장)
    connectTimeoutMS: 10000          # 연결 타임아웃 10초 (추가 권장)

  weaviate:
    timeout: 30                # 쿼리 타임아웃 30초 (적용 필요)
    connect_timeout: 10        # 연결 타임아웃 10초 (추가 권장)
```

---

## 7. 연결 누수 가능성 분석

### 7.1 PostgreSQL (DatabaseManager)
**위험도**: 🟢 **낮음**

✅ **방지 메커니즘**:
- Context Manager 패턴 (`get_session`)
- Try-Finally로 항상 세션 종료
- SQLAlchemy Connection Pool 자동 관리

⚠️ **주의 사항**:
- `get_db()` 의존성 주입 시 제너레이터 사용 필수
- 수동으로 세션 생성 시 누수 가능

### 7.2 MongoDB (MongoDBClient)
**위험도**: 🟡 **중간**

✅ **방지 메커니즘**:
- pymongo 내부 Connection Pool 자동 관리
- 싱글톤 패턴으로 단일 클라이언트 공유

⚠️ **위험 요소**:
- `get_collection()` 반환 후 커서 미종료 가능
- Cursor iteration 중단 시 리소스 점유

**권장 사항**:
```python
# 커서 사용 시 Context Manager 권장
async with collection.find(filter) as cursor:
    async for doc in cursor:
        process(doc)
```

### 7.3 Weaviate (WeaviateClient, WeaviateVectorStore)
**위험도**: 🟡 **중간**

✅ **방지 메커니즘**:
- `__del__` 매직 메서드로 자동 정리
- 싱글톤 패턴

⚠️ **위험 요소**:
- `WeaviateVectorStore` 중복 인스턴스 생성 가능 (싱글톤 아님)
- gRPC 연결 누수 감지 어려움

**권장 사항**:
```python
# WeaviateVectorStore도 싱글톤 적용 고려
class WeaviateVectorStore(IVectorStore):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

---

## 8. 권장 사항 종합

### 🔴 High Priority (즉시 적용 권장)

1. **PostgreSQL Timeout 설정 추가**
   ```python
   # connection.py
   self.engine = create_async_engine(
       database_url,
       pool_pre_ping=True,
       pool_size=5,
       max_overflow=10,
       connect_args={"timeout": 10},
       pool_timeout=30,
       pool_recycle=3600,
   )
   ```

2. **Cleanup Timeout 추가**
   ```python
   # di_container.py
   async def cleanup_with_timeout(coro, timeout=10):
       await asyncio.wait_for(coro, timeout=timeout)
   ```

3. **Weaviate Timeout 적용**
   ```python
   # weaviate_client.py
   connection_params = ConnectionParams.from_url(
       url, grpc_port,
       timeout_config=weaviate.TimeoutConfig(query=timeout)
   )
   ```

### 🟡 Medium Priority (v3.4.0 계획)

4. **Connection Pool 모니터링**
   ```python
   # Health Check API에 추가
   @router.get("/health/db")
   async def db_health():
       return {
           "postgres": {
               "pool_size": db_manager.engine.pool.size(),
               "checked_in": db_manager.engine.pool.checkedin(),
           },
           "mongodb": mongodb_client.get_pool_stats(),
       }
   ```

5. **Weaviate 재시도 로직**
   ```python
   @tenacity.retry(stop=tenacity.stop_after_attempt(3))
   def _connect_with_retry(self):
       self._client.connect()
   ```

6. **MongoDB 커서 자동 종료**
   ```python
   # Context Manager로 커서 관리
   @contextmanager
   def safe_cursor(collection, filter):
       cursor = collection.find(filter)
       try:
           yield cursor
       finally:
           cursor.close()
   ```

### 🟢 Low Priority (모니터링 개선)

7. **연결 누수 알림**
   - Prometheus 메트릭 추가
   - 임계값 초과 시 Slack 알림

8. **자동 Health Check**
   - 5분마다 `is_ready()` 호출
   - 실패 시 자동 재연결

---

## 9. 테스트 커버리지 분석

### 9.1 현재 테스트 현황
```bash
# 테스트 검색 결과
tests/unit/retrieval/retrievers/test_weaviate_retriever.py
tests/unit/retrieval/retrievers/test_mongodb_retriever.py
tests/unit/mcp/test_weaviate_tools.py
```

**평가**: ⚠️ **인프라 연결 관리 테스트 부족**

### 9.2 추가 필요 테스트

1. **PostgreSQL Connection Pool Test**
   ```python
   # tests/infrastructure/test_postgres_pool.py
   async def test_pool_exhaustion():
       # Pool size 초과 시 대기 확인
       pass

   async def test_pool_recovery():
       # 연결 실패 후 복구 확인
       pass
   ```

2. **MongoDB Connection Leak Test**
   ```python
   # tests/infrastructure/test_mongodb_leak.py
   async def test_cursor_leak():
       # 커서 미종료 시 리소스 확인
       pass
   ```

3. **Weaviate Retry Test**
   ```python
   # tests/infrastructure/test_weaviate_retry.py
   async def test_connection_retry():
       # 재시도 로직 검증
       pass
   ```

---

## 10. 결론 및 최종 권장 사항

### 10.1 종합 평가

| 영역 | 평가 | 점수 |
|------|------|------|
| Connection Pooling | 우수 | 9/10 |
| Timeout 처리 | 부족 | 5/10 |
| Graceful Shutdown | 우수 | 9/10 |
| 연결 누수 방지 | 양호 | 7/10 |
| 에러 핸들링 | 우수 | 9/10 |
| 모니터링 | 부족 | 4/10 |

**종합 점수**: **7.2/10 (B+)**

### 10.2 최종 권장 사항

#### 즉시 적용 (v3.3.1 Hotfix)
1. PostgreSQL에 `connect_timeout`, `pool_timeout`, `pool_recycle` 추가
2. DI Container cleanup에 timeout 적용
3. Weaviate timeout 설정 실제 적용

#### 단기 계획 (v3.4.0)
4. Connection Pool 모니터링 API 추가
5. Weaviate 연결 재시도 로직 구현
6. 커서 자동 종료 헬퍼 함수 제공

#### 장기 계획 (v4.0.0)
7. Prometheus 메트릭 연동
8. 자동 Health Check 및 재연결
9. 포괄적인 인프라 테스트 Suite

### 10.3 보안 고려 사항
- PostgresMetadataStore WHERE 절 컬럼명 검증 추가
- MongoDB 연결 문자열 환경 변수 마스킹 강화 (현재 로그에 일부 노출 가능)

---

## 📚 참고 자료

- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [pymongo Connection Pool](https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html)
- [Weaviate Python Client](https://weaviate.io/developers/weaviate/client-libraries/python)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

---

**문서 버전**: 1.0
**다음 리뷰 예정일**: 2026-02-08
