# PostgreSQL 마이그레이션 가이드

배치 크롤링 시스템을 위한 PostgreSQL 테이블 생성 및 초기 데이터 설정 가이드

## 📋 마이그레이션 파일

### 1. `002_create_batch_tables.sql`
배치 시스템 테이블 3개 생성:
- `batch_runs`: 배치 실행 이력
- `batch_source_logs`: 소스별 크롤링 로그
- `parsing_rules`: 파싱 규칙 저장소

**생성되는 테이블**:
```sql
batch_runs (7 columns)
  - run_id (UUID, PK)
  - started_at (TIMESTAMP WITH TIME ZONE)
  - completed_at (TIMESTAMP WITH TIME ZONE)
  - status (VARCHAR)
  - total_duration_seconds (INTEGER)
  - successful_sources (INTEGER)
  - created_at (TIMESTAMP WITH TIME ZONE)

batch_source_logs (10 columns)
  - log_id (UUID, PK)
  - run_id (UUID, FK)
  - source_url (TEXT)
  - source_name (VARCHAR)
  - chunks_created (INTEGER)
  - validation_passed (BOOLEAN)
  - html_structure_hash (VARCHAR)
  - structure_changed (BOOLEAN)
  - error_message (TEXT)
  - duration_seconds (INTEGER)
  - created_at (TIMESTAMP WITH TIME ZONE)

parsing_rules (8 columns)
  - rule_id (UUID, PK)
  - source_url (TEXT, UNIQUE)
  - source_name (VARCHAR)
  - content_selector (TEXT)
  - remove_selectors (JSONB)
  - validation_config (JSONB)
  - last_verified_at (TIMESTAMP WITH TIME ZONE)
  - created_at (TIMESTAMP WITH TIME ZONE)
  - updated_at (TIMESTAMP WITH TIME ZONE)
```

**생성되는 인덱스**: 8개
- `idx_batch_runs_started_at`: 시간 기반 조회 최적화
- `idx_batch_runs_status`: 상태별 조회 최적화
- `idx_batch_source_logs_run_id`: 배치 실행별 로그 조회
- `idx_batch_source_logs_source_url`: 소스별 로그 조회
- `idx_batch_source_logs_source_name`: 소스명 기반 조회
- `idx_batch_source_logs_structure_changed`: 구조 변경 감지
- `idx_parsing_rules_source_url`: UNIQUE 인덱스
- `idx_parsing_rules_source_name`: 소스명 조회

### 2. `003_insert_initial_parsing_rules.sql`
샘플 데이터 소스의 초기 파싱 규칙 삽입:
1. **notion_page_1**: Notion 페이지 (예시)
2. **external_guide**: 외부 가이드 페이지 (예시)
3. **external_faq**: FAQ 페이지 (예시)

## 🚀 실행 방법

### 로컬 환경 (Docker PostgreSQL)

```bash
# 1. PostgreSQL 컨테이너 연결
docker exec -it postgres_container psql -U your_username -d your_database

# 2. 테이블 생성
\i /path/to/scripts/migrations/002_create_batch_tables.sql

# 3. 초기 데이터 삽입
\i /path/to/scripts/migrations/003_insert_initial_parsing_rules.sql
```

### Railway 환경

```bash
# 1. Railway DATABASE_URL 가져오기
railway variables get DATABASE_URL

# 2. psql로 연결
psql "postgresql://username:password@host:port/database"

# 3. 로컬 파일 실행
\i scripts/migrations/002_create_batch_tables.sql
\i scripts/migrations/003_insert_initial_parsing_rules.sql

# 또는 파일 내용을 복사해서 직접 실행
```

### Python 스크립트로 실행 (권장)

```bash
# 실행 스크립트 작성 (scripts/setup_batch_tables.py)
python scripts/setup_batch_tables.py
```

스크립트 예시:
```python
#!/usr/bin/env python3
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# DATABASE_URL 환경변수에서 가져오기
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL 환경변수가 설정되지 않음")

# SQLAlchemy 엔진 생성
engine = create_engine(database_url)

# 마이그레이션 파일 경로
migrations_dir = Path(__file__).parent / "migrations"

# 실행할 SQL 파일 목록
sql_files = [
    "002_create_batch_tables.sql",
    "003_insert_initial_parsing_rules.sql",
]

# 각 SQL 파일 실행
with engine.connect() as conn:
    for sql_file in sql_files:
        file_path = migrations_dir / sql_file
        print(f"📄 실행 중: {sql_file}")

        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 트랜잭션으로 실행
        trans = conn.begin()
        try:
            conn.execute(text(sql_content))
            trans.commit()
            print(f"✅ 완료: {sql_file}")
        except Exception as e:
            trans.rollback()
            print(f"❌ 실패: {sql_file} - {e}")
            raise

print("✅ 모든 마이그레이션 완료!")
```

## ⚠️ 주의사항

### 1. 실제 크롤링 소스 URL 수정 필요
`003_insert_initial_parsing_rules.sql`의 샘플 URL을 실제 크롤링 소스로 교체하세요:

```sql
-- 수정 전 (샘플)
source_url = 'https://www.notion.so/example-page-1'

-- 수정 후 (실제)
source_url = 'https://your-actual-notion-page-url'
```

### 2. CSS Selector 검증
각 소스의 실제 HTML 구조를 분석하여 올바른 CSS Selector를 설정하세요:

```python
# HTML 구조 분석 스크립트 예시
from bs4 import BeautifulSoup
import requests

url = "https://your-target-site.com"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# 메인 콘텐츠 선택자 찾기
main_content = soup.select('article.content')  # 예시
print(main_content)

# 제거할 요소 찾기
unwanted = soup.select('nav, footer, .ad-banner')
print(unwanted)
```

### 3. Validation Config 조정
실제 크롤링 결과에 맞게 min_chunks, max_chunks를 조정하세요:

```sql
-- 예시: 실제 크롤링 후 평균 30개 청크 생성 시
validation_config = '{"min_chunks": 20, "max_chunks": 40}'::jsonb
```

## 📊 데이터 검증

### 테이블 생성 확인
```sql
-- 테이블 목록 조회
\dt

-- 테이블 구조 확인
\d batch_runs
\d batch_source_logs
\d parsing_rules

-- 인덱스 확인
\di
```

### 초기 데이터 확인
```sql
-- 파싱 규칙 개수 확인
SELECT COUNT(*) FROM parsing_rules;

-- 파싱 규칙 목록 조회
SELECT source_name, source_url, content_selector
FROM parsing_rules
ORDER BY source_name;
```

## 🔧 트러블슈팅

### 문제 1: `relation "batch_runs" already exists`
**원인**: 테이블이 이미 존재함
**해결**:
```sql
-- 테이블 삭제 후 재생성 (주의: 데이터 손실)
DROP TABLE IF EXISTS batch_source_logs CASCADE;
DROP TABLE IF EXISTS batch_runs CASCADE;
DROP TABLE IF EXISTS parsing_rules CASCADE;

-- 또는 CREATE TABLE IF NOT EXISTS 사용 (스크립트에 이미 포함됨)
```

### 문제 2: `permission denied for schema public`
**원인**: 권한 부족
**해결**:
```sql
-- 권한 부여 (관리자 계정으로 실행)
GRANT ALL PRIVILEGES ON SCHEMA public TO your_username;
```

### 문제 3: `constraint "fk_batch_source_logs_run_id" already exists`
**원인**: Foreign Key 제약조건이 이미 존재
**해결**: 스크립트의 `CREATE TABLE IF NOT EXISTS` 구문이 이미 처리함. 수동으로 제거 필요 시:
```sql
ALTER TABLE batch_source_logs DROP CONSTRAINT IF EXISTS fk_batch_source_logs_run_id;
```

## 📝 다음 단계

1. **파싱 규칙 검증**: 실제 HTML 구조 분석 후 selector 수정
2. **배치 크롤링 스크립트 개발**: `parsing_rules` 테이블 참조하여 크롤링
3. **로깅 구현**: `batch_runs`, `batch_source_logs` 테이블에 실행 결과 기록
4. **모니터링 대시보드**: 배치 실행 상태 및 구조 변경 감지 시각화

## 🔗 참고 파일

- `app/database/models.py` - SQLAlchemy 모델 정의 (추후 추가)
- `scripts/batch_crawler.py` - 배치 크롤링 스크립트 (추후 개발)
- `CLAUDE.md` - 프로젝트 개발 가이드라인

---

**마지막 업데이트**: 2025-11-19
**담당자**: PostgreSQL 인프라 설계자
