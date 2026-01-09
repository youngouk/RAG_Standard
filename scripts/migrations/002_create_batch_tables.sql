-- ============================================================================
-- 배치 시스템 테이블 생성 스크립트
-- ============================================================================
-- 목적: 배치 크롤링 실행 이력, 소스별 로그, 파싱 규칙 저장
-- 작성일: 2025-11-19
-- ============================================================================

-- ============================================================================
-- 1. batch_runs 테이블: 배치 실행 정보
-- ============================================================================
CREATE TABLE IF NOT EXISTS batch_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'partial_failure', 'failure')),
    total_duration_seconds INTEGER,
    successful_sources INTEGER DEFAULT 0 CHECK (successful_sources >= 0 AND successful_sources <= 6),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 성능 최적화: 시간 기반 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_runs_started_at ON batch_runs(started_at DESC);

-- 상태별 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_runs_status ON batch_runs(status);

-- ============================================================================
-- 2. batch_source_logs 테이블: 개별 소스별 실행 로그
-- ============================================================================
CREATE TABLE IF NOT EXISTS batch_source_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    source_url TEXT NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    chunks_created INTEGER DEFAULT 0 CHECK (chunks_created >= 0),
    validation_passed BOOLEAN NOT NULL DEFAULT FALSE,
    html_structure_hash VARCHAR(64),
    structure_changed BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    duration_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Foreign Key 제약조건
    CONSTRAINT fk_batch_source_logs_run_id
        FOREIGN KEY (run_id)
        REFERENCES batch_runs(run_id)
        ON DELETE CASCADE
);

-- 성능 최적화: run_id 기반 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_source_logs_run_id ON batch_source_logs(run_id);

-- 소스별 로그 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_source_logs_source_url ON batch_source_logs(source_url);

-- 소스명 기반 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_source_logs_source_name ON batch_source_logs(source_name);

-- 구조 변경 감지를 위한 복합 인덱스
CREATE INDEX IF NOT EXISTS idx_batch_source_logs_structure_changed
    ON batch_source_logs(source_url, structure_changed);

-- ============================================================================
-- 3. parsing_rules 테이블: 수동 분석된 파싱 규칙
-- ============================================================================
CREATE TABLE IF NOT EXISTS parsing_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url TEXT NOT NULL UNIQUE,
    source_name VARCHAR(100) NOT NULL,
    content_selector TEXT NOT NULL,
    remove_selectors JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- UNIQUE 제약조건을 위한 인덱스 (이미 UNIQUE 제약으로 자동 생성되지만 명시)
CREATE UNIQUE INDEX IF NOT EXISTS idx_parsing_rules_source_url ON parsing_rules(source_url);

-- 소스명 기반 조회를 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_parsing_rules_source_name ON parsing_rules(source_name);

-- ============================================================================
-- 트리거: updated_at 자동 갱신
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- parsing_rules 테이블에 트리거 적용
DROP TRIGGER IF EXISTS trigger_update_parsing_rules_updated_at ON parsing_rules;
CREATE TRIGGER trigger_update_parsing_rules_updated_at
    BEFORE UPDATE ON parsing_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 코멘트 추가 (문서화)
-- ============================================================================
COMMENT ON TABLE batch_runs IS '배치 크롤링 실행 이력 테이블 (UTC 타임존 사용)';
COMMENT ON COLUMN batch_runs.run_id IS '배치 실행 고유 ID';
COMMENT ON COLUMN batch_runs.status IS '배치 실행 상태: running(실행 중), success(성공), partial_failure(일부 실패), failure(전체 실패)';
COMMENT ON COLUMN batch_runs.successful_sources IS '성공한 소스 개수 (최대 6개)';

COMMENT ON TABLE batch_source_logs IS '개별 소스별 배치 크롤링 로그';
COMMENT ON COLUMN batch_source_logs.html_structure_hash IS 'HTML 구조 변경 감지를 위한 해시값 (SHA256)';
COMMENT ON COLUMN batch_source_logs.structure_changed IS 'HTML 구조 변경 여부 (파싱 규칙 재검토 필요)';
COMMENT ON COLUMN batch_source_logs.validation_passed IS '청크 개수 validation 통과 여부';

COMMENT ON TABLE parsing_rules IS '수동 분석된 크롤링 파싱 규칙 저장소';
COMMENT ON COLUMN parsing_rules.content_selector IS '콘텐츠 추출을 위한 CSS Selector';
COMMENT ON COLUMN parsing_rules.remove_selectors IS '제거할 선택자 배열 (JSONB)';
COMMENT ON COLUMN parsing_rules.validation_config IS '청크 개수 검증 설정 (예: {"min_chunks": 1, "max_chunks": 100})';
COMMENT ON COLUMN parsing_rules.last_verified_at IS '마지막으로 파싱 규칙이 검증된 시간';

-- ============================================================================
-- 완료 메시지
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ 배치 시스템 테이블 생성 완료';
    RAISE NOTICE '   - batch_runs';
    RAISE NOTICE '   - batch_source_logs';
    RAISE NOTICE '   - parsing_rules';
    RAISE NOTICE '   - 인덱스 8개 생성';
    RAISE NOTICE '   - updated_at 자동 갱신 트리거 설정';
END $$;
