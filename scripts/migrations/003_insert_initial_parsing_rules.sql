-- ============================================================================
-- 초기 파싱 규칙 데이터 삽입 스크립트 (샘플)
-- ============================================================================
-- 목적: parsing_rules 테이블에 예시 규칙을 삽입하여 구조/쿼리를 검증
-- 작성일: 2025-11-19
-- 주의: 실제 크롤링 소스에 맞게 selector와 validation_config를 조정해야 함
-- ============================================================================

-- ============================================================================
-- 1. Notion 페이지 (예시)
-- ============================================================================
INSERT INTO parsing_rules (
    source_url,
    source_name,
    content_selector,
    remove_selectors,
    validation_config,
    last_verified_at
) VALUES (
    'https://www.notion.so/example-page-1',
    'notion_page_1',
    'article',
    '["nav", "footer"]'::jsonb,
    '{"min_chunks": 1, "max_chunks": 200, "expected_content_length": 500}'::jsonb,
    NOW()
) ON CONFLICT (source_url) DO UPDATE SET
    content_selector = EXCLUDED.content_selector,
    remove_selectors = EXCLUDED.remove_selectors,
    validation_config = EXCLUDED.validation_config,
    last_verified_at = NOW();

-- ============================================================================
-- 2. 외부 가이드 페이지 (예시)
-- ============================================================================
INSERT INTO parsing_rules (
    source_url,
    source_name,
    content_selector,
    remove_selectors,
    validation_config,
    last_verified_at
) VALUES (
    'https://example.com/guide',
    'external_guide',
    'main, article',
    '["header", "footer", "nav", ".ad"]'::jsonb,
    '{"min_chunks": 1, "max_chunks": 300, "expected_content_length": 800}'::jsonb,
    NOW()
) ON CONFLICT (source_url) DO UPDATE SET
    content_selector = EXCLUDED.content_selector,
    remove_selectors = EXCLUDED.remove_selectors,
    validation_config = EXCLUDED.validation_config,
    last_verified_at = NOW();

-- ============================================================================
-- 3. FAQ 페이지 (예시)
-- ============================================================================
INSERT INTO parsing_rules (
    source_url,
    source_name,
    content_selector,
    remove_selectors,
    validation_config,
    last_verified_at
) VALUES (
    'https://example.org/faq',
    'external_faq',
    'main',
    '["header", "footer"]'::jsonb,
    '{"min_chunks": 1, "max_chunks": 200, "expected_content_length": 500}'::jsonb,
    NOW()
) ON CONFLICT (source_url) DO UPDATE SET
    content_selector = EXCLUDED.content_selector,
    remove_selectors = EXCLUDED.remove_selectors,
    validation_config = EXCLUDED.validation_config,
    last_verified_at = NOW();


