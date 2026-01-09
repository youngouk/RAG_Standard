# 배치 시스템 PostgreSQL 설정 완료 보고서

**작성일**: 2025-11-19
**작성자**: PostgreSQL 인프라 설계자

---

## 📊 작업 요약

배치 크롤링 시스템을 위한 PostgreSQL 테이블 3개와 SQLAlchemy 모델을 성공적으로 설계 및 구현했습니다.

### 생성된 파일

| 파일 경로 | 목적 | 크기 |
|----------|------|------|
| `scripts/migrations/002_create_batch_tables.sql` | 테이블 및 인덱스 DDL | 6.4 KB |
| `scripts/migrations/003_insert_initial_parsing_rules.sql` | 초기 데이터 삽입 | 7.7 KB |
| `scripts/migrations/README.md` | 마이그레이션 가이드 | 7.5 KB |
| `scripts/setup_batch_tables.py` | Python 실행 스크립트 | 7.8 KB |
| `app/database/models.py` | SQLAlchemy 모델 추가 | +288 lines |

---

## 🗄️ 테이블 설계 상세

### 1. `batch_runs` 테이블
**목적**: 배치 실행 이력 저장

**컬럼 (7개)**:
```sql
run_id                  UUID (PK)                  -- 배치 실행 고유 ID
started_at              TIMESTAMP WITH TIME ZONE   -- 시작 시간 (UTC)
completed_at            TIMESTAMP WITH TIME ZONE   -- 완료 시간 (NULL 가능)
status                  VARCHAR(20)                -- 'success', 'partial_failure', 'failure'
total_duration_seconds  INTEGER                    -- 총 실행 시간 (초)
successful_sources      INTEGER                    -- 성공한 소스 개수 (0-6)
created_at              TIMESTAMP WITH TIME ZONE   -- 레코드 생성 시간
```

**인덱스 (2개)**:
- `idx_batch_runs_started_at`: 시간 기반 조회 최적화
- `idx_batch_runs_status`: 상태별 필터링 최적화

**제약조건**:
- `status` CHECK: 'success', 'partial_failure', 'failure' 중 하나
- `successful_sources` CHECK: 0 이상 6 이하

**사용 예시**:
```python
# 배치 실행 기록
batch_run = BatchRunModel(
    started_at=datetime.now(timezone.utc),
    status='success',
    total_duration_seconds=120,
    successful_sources=6
)
```

---

### 2. `batch_source_logs` 테이블
**목적**: 개별 소스별 크롤링 로그

**컬럼 (10개)**:
```sql
log_id                UUID (PK)                  -- 로그 고유 ID
run_id                UUID (FK → batch_runs)     -- 배치 실행 ID
source_url            TEXT                       -- 크롤링 소스 URL
source_name           VARCHAR(100)               -- 소스명 (예: notion_page_1)
chunks_created        INTEGER                    -- 생성된 청크 개수
validation_passed     BOOLEAN                    -- 청크 검증 통과 여부
html_structure_hash   VARCHAR(64)                -- HTML 구조 해시 (SHA256)
structure_changed     BOOLEAN                    -- 구조 변경 감지
error_message         TEXT                       -- 에러 메시지 (NULL 가능)
duration_seconds      INTEGER                    -- 실행 시간 (초)
created_at            TIMESTAMP WITH TIME ZONE   -- 레코드 생성 시간
```

**인덱스 (4개)**:
- `idx_batch_source_logs_run_id`: 배치별 로그 조회
- `idx_batch_source_logs_source_url`: 소스 URL 기반 조회
- `idx_batch_source_logs_source_name`: 소스명 기반 조회
- `idx_batch_source_logs_structure_changed`: 구조 변경 감지 복합 인덱스

**Foreign Key**:
- `run_id` → `batch_runs.run_id` (ON DELETE CASCADE)

**사용 예시**:
```python
# 소스별 로그 기록
log = BatchSourceLogModel(
    run_id=batch_run.run_id,
    source_url='https://www.notion.so/...',
    source_name='notion_page_1',
    chunks_created=45,
    validation_passed=True,
    html_structure_hash='abc123...',
    structure_changed=False,
    duration_seconds=30
)
```

---

### 3. `parsing_rules` 테이블
**목적**: 수동 분석된 파싱 규칙 저장소

**컬럼 (8개)**:
```sql
rule_id              UUID (PK)                  -- 규칙 고유 ID
source_url           TEXT (UNIQUE)              -- 크롤링 소스 URL (고유)
source_name          VARCHAR(100)               -- 소스명
content_selector     TEXT                       -- CSS Selector (메인 콘텐츠)
remove_selectors     JSONB                      -- 제거할 선택자 배열
validation_config    JSONB                      -- 청크 검증 설정
last_verified_at     TIMESTAMP WITH TIME ZONE   -- 마지막 검증 시간
created_at           TIMESTAMP WITH TIME ZONE   -- 생성 시간
updated_at           TIMESTAMP WITH TIME ZONE   -- 수정 시간 (자동 갱신)
```

**인덱스 (2개)**:
- `idx_parsing_rules_source_url`: UNIQUE 인덱스
- `idx_parsing_rules_source_name`: 소스명 조회

**트리거**:
- `update_updated_at_column()`: UPDATE 시 `updated_at` 자동 갱신

**JSONB 필드 예시**:
```json
// remove_selectors
["nav", "footer", ".ad-banner", "#popup"]

// validation_config
{
  "min_chunks": 5,
  "max_chunks": 50,
  "expected_content_length": 1000
}
```

**사용 예시**:
```python
# 파싱 규칙 조회
rule = session.query(ParsingRuleModel).filter_by(
    source_name='notion_page_1'
).first()

print(rule.content_selector)      # 'article.notion-page-content'
print(rule.validation_config)     # {'min_chunks': 5, 'max_chunks': 50}
```

---

## 🔧 SQLAlchemy 모델

### `BatchRunModel`
```python
from app.database.models import BatchRunModel

# 배치 실행 생성
batch = BatchRunModel(
    started_at=datetime.now(timezone.utc),
    status='success',
    successful_sources=6
)
session.add(batch)
session.commit()

# 딕셔너리 변환
batch_dict = batch.to_dict()
```

### `BatchSourceLogModel`
```python
from app.database.models import BatchSourceLogModel

# 소스 로그 생성
log = BatchSourceLogModel(
    run_id=batch.run_id,
    source_name='notion_page_1',
    chunks_created=45,
    validation_passed=True
)
session.add(log)
session.commit()
```

### `ParsingRuleModel`
```python
from app.database.models import ParsingRuleModel

# 파싱 규칙 조회
rule = session.query(ParsingRuleModel).filter_by(
    source_name='external_guide'
).first()

# 규칙 업데이트 (updated_at 자동 갱신)
rule.content_selector = 'main.new-selector'
session.commit()
```

---

## 🚀 설치 가이드

### 1. 로컬 환경 (빠른 테스트)

```bash
# DATABASE_URL 설정
export DATABASE_URL="postgresql://user:password@localhost:5432/database"

# Python 스크립트 실행
python scripts/setup_batch_tables.py
```

**예상 출력**:
```
======================================================================
🚀 배치 시스템 PostgreSQL 테이블 생성 시작
======================================================================
✅ DATABASE_URL 확인 완료
✅ PostgreSQL 연결 성공

📊 마이그레이션 실행 중...

📄 실행 중: 002_create_batch_tables.sql
✅ 완료: 002_create_batch_tables.sql
📄 실행 중: 003_insert_initial_parsing_rules.sql
✅ 완료: 003_insert_initial_parsing_rules.sql

📊 검증 중...

🔍 테이블 생성 검증 중...
✅ 생성된 테이블: batch_runs, batch_source_logs, parsing_rules
✅ 초기 파싱 규칙: 3개 소스
✅ 생성된 인덱스: 8개

======================================================================
✅ 배치 시스템 테이블 생성 완료!
======================================================================
```

### 2. Railway 환경

```bash
# 1. Railway DATABASE_URL 가져오기
railway variables get DATABASE_URL

# 2. 환경변수 설정
export DATABASE_URL="postgresql://..."

# 3. 스크립트 실행
python scripts/setup_batch_tables.py
```

---

## 📋 초기 데이터

### 초기 파싱 규칙 (샘플)

| 번호 | source_name | source_url | content_selector |
|------|-------------|------------|------------------|
| 1 | notion_page_1 | https://www.notion.so/example-page-1 | article |
| 2 | external_guide | https://example.com/guide | main, article |
| 3 | external_faq | https://example.org/faq | main |

⚠️ **주의**: 이 데이터는 샘플입니다. 실제 크롤링 소스로 교체해야 합니다.

---

## ⚠️ 필수 후속 작업

### 1. 실제 크롤링 소스 URL 수정 (최우선)
```sql
-- 예시: Notion 페이지 실제 URL로 변경
UPDATE parsing_rules
SET source_url = 'https://your-actual-notion-page-url',
    last_verified_at = NOW()
WHERE source_name = 'notion_page_1';
```

### 2. CSS Selector 검증
각 소스의 실제 HTML 구조를 분석하여 올바른 선택자 설정:

```python
# HTML 구조 분석 스크립트
from bs4 import BeautifulSoup
import requests

url = "https://your-target-site.com"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# 메인 콘텐츠 찾기
main_content = soup.select('article.content')
print(main_content)
```

### 3. Validation Config 조정
실제 크롤링 후 평균 청크 개수에 맞게 조정:

```sql
-- 예시: 평균 30개 청크 생성 시
UPDATE parsing_rules
SET validation_config = '{"min_chunks": 20, "max_chunks": 40, "expected_content_length": 1500}'::jsonb
WHERE source_name = 'notion_page_1';
```

### 4. 배치 크롤링 스크립트 개발
`parsing_rules` 테이블을 참조하여 자동 크롤링:

```python
# 예시 구조 (scripts/batch_crawler.py)
async def run_batch_crawling():
    # 1. parsing_rules 테이블에서 규칙 가져오기
    rules = session.query(ParsingRuleModel).all()

    # 2. batch_runs 레코드 생성
    batch_run = BatchRunModel(started_at=datetime.now(timezone.utc))

    # 3. 각 소스별 크롤링
    for rule in rules:
        try:
            # 크롤링 로직
            chunks = crawl_source(rule)

            # 로그 기록
            log = BatchSourceLogModel(
                run_id=batch_run.run_id,
                source_name=rule.source_name,
                chunks_created=len(chunks),
                validation_passed=validate_chunks(chunks, rule)
            )
        except Exception as e:
            # 에러 로그 기록
            log.error_message = str(e)
```

---

## 🔍 데이터 검증 쿼리

### 테이블 구조 확인
```sql
-- 테이블 목록
\dt

-- 테이블 구조
\d batch_runs
\d batch_source_logs
\d parsing_rules

-- 인덱스 확인
\di
```

### 데이터 조회
```sql
-- 파싱 규칙 전체 조회
SELECT source_name, source_url, content_selector
FROM parsing_rules
ORDER BY source_name;

-- 최근 배치 실행 이력 (최근 10개)
SELECT run_id, started_at, status, successful_sources
FROM batch_runs
ORDER BY started_at DESC
LIMIT 10;

-- 구조 변경 감지된 소스 조회
SELECT source_name, source_url, created_at
FROM batch_source_logs
WHERE structure_changed = TRUE
ORDER BY created_at DESC;
```

---

## 🔗 관련 파일

### 마이그레이션 파일
- `scripts/migrations/002_create_batch_tables.sql` - DDL 스크립트
- `scripts/migrations/003_insert_initial_parsing_rules.sql` - 초기 데이터
- `scripts/migrations/README.md` - 마이그레이션 가이드

### Python 코드
- `scripts/setup_batch_tables.py` - 자동 설치 스크립트
- `app/database/models.py` - SQLAlchemy 모델 (line 478-761)

### 프로젝트 문서
- `CLAUDE.md` - 프로젝트 개발 가이드라인

---

## ✅ 체크리스트

완료된 작업:
- [x] 테이블 DDL 스크립트 작성 (002_create_batch_tables.sql)
- [x] 초기 데이터 삽입 스크립트 작성 (003_insert_initial_parsing_rules.sql)
- [x] Python 실행 스크립트 작성 (setup_batch_tables.py)
- [x] SQLAlchemy 모델 정의 (BatchRunModel, BatchSourceLogModel, ParsingRuleModel)
- [x] 인덱스 설계 (8개)
- [x] Foreign Key 제약조건 설정
- [x] Check Constraint 설정
- [x] updated_at 자동 갱신 트리거
- [x] 마이그레이션 가이드 문서 작성

필수 후속 작업:
- [ ] 실제 크롤링 소스 URL 확인 및 수정
- [ ] CSS Selector 검증 (실제 HTML 구조 분석)
- [ ] Validation Config 최적화 (실제 청크 개수 기반)
- [ ] 배치 크롤링 스크립트 개발
- [ ] 모니터링 대시보드 구현
- [ ] 구조 변경 감지 알림 시스템 구현

---

**작성 완료**: 2025-11-19 12:35 KST
**PostgreSQL 인프라 설계자**
