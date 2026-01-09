-- =====================================================
-- Prompts 테이블 생성 마이그레이션 (Phase 1)
-- =====================================================
-- 프롬프트 데이터를 PostgreSQL에 저장하기 위한 테이블
-- 기존 JSON 파일 방식에서 마이그레이션

-- 테이블 생성 (IF NOT EXISTS로 안전하게)
CREATE TABLE IF NOT EXISTS prompts (
    -- Primary Key (UUID 형식 문자열)
    id VARCHAR PRIMARY KEY,

    -- 프롬프트 기본 정보
    name VARCHAR UNIQUE NOT NULL,
    content TEXT NOT NULL,
    description TEXT,

    -- 분류 및 상태
    category VARCHAR NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- 메타데이터 (JSON 필드로 확장 가능)
    extra_metadata JSONB DEFAULT '{}',

    -- 타임스탬프
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 인덱스 생성 (쿼리 최적화)
CREATE INDEX IF NOT EXISTS idx_prompts_name ON prompts(name);
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(category);
CREATE INDEX IF NOT EXISTS idx_prompts_is_active ON prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_category_active ON prompts(category, is_active);
CREATE INDEX IF NOT EXISTS idx_updated_at ON prompts(updated_at);
CREATE INDEX IF NOT EXISTS idx_created_at ON prompts(created_at);

-- 코멘트 추가 (문서화)
COMMENT ON TABLE prompts IS '프롬프트 데이터 테이블 (JSON 파일에서 마이그레이션)';
COMMENT ON COLUMN prompts.id IS '프롬프트 고유 ID (UUID)';
COMMENT ON COLUMN prompts.name IS '프롬프트 이름 (고유)';
COMMENT ON COLUMN prompts.content IS '프롬프트 내용';
COMMENT ON COLUMN prompts.description IS '프롬프트 설명';
COMMENT ON COLUMN prompts.category IS '프롬프트 카테고리 (system, style 등)';
COMMENT ON COLUMN prompts.is_active IS '활성화 여부';
COMMENT ON COLUMN prompts.extra_metadata IS '추가 메타데이터 (JSON)';
COMMENT ON COLUMN prompts.created_at IS '생성 시간';
COMMENT ON COLUMN prompts.updated_at IS '수정 시간';

-- 업데이트 타임스탬프 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_prompts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_prompts_timestamp ON prompts;
CREATE TRIGGER trigger_update_prompts_timestamp
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_prompts_updated_at();

-- 테이블 정보 확인 (실행 후 검증용)
DO $$
BEGIN
    RAISE NOTICE '✅ prompts 테이블 생성 완료';
    RAISE NOTICE '📊 테이블 구조:';
    RAISE NOTICE '  - id: VARCHAR (PK)';
    RAISE NOTICE '  - name: VARCHAR UNIQUE';
    RAISE NOTICE '  - content: TEXT';
    RAISE NOTICE '  - description: TEXT';
    RAISE NOTICE '  - category: VARCHAR (default: system)';
    RAISE NOTICE '  - is_active: BOOLEAN (default: true)';
    RAISE NOTICE '  - extra_metadata: JSONB';
    RAISE NOTICE '  - created_at: TIMESTAMP WITH TIME ZONE';
    RAISE NOTICE '  - updated_at: TIMESTAMP WITH TIME ZONE (자동 갱신)';
END $$;
