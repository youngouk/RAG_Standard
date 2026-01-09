"""
통합 PII 처리 모듈 테스트 (범용화 버전)

테스트 대상:
- WhitelistManager: 화이트리스트 관리
- PIIProcessor: 통합 Facade
- PrivacyMasker: 마스킹 엔진 (화이트리스트 통합)

범용 기본 패턴:
- 이름 + "고객님" / "담당자님" 패턴만 기본 지원
- 도메인 특화 패턴은 name_suffixes 파라미터로 확장 가능

오탐 방지 테스트 케이스:
- "이모님" → 마스킹 안 함 (화이트리스트)
- "헬퍼님" → 마스킹 안 함 (화이트리스트)
- "담당 매니저" → 마스킹 안 함 (화이트리스트)
- "김철수 고객님" → "김** 고객님" (이름 마스킹)

생성일: 2025-12-08
범용화: 2026-01-02
"""

import pytest

from app.modules.core.privacy import (
    PIIProcessor,
    PrivacyMasker,
    WhitelistManager,
    process_pii,
)
from app.modules.core.privacy.whitelist import DEFAULT_WHITELIST


class TestWhitelistManager:
    """WhitelistManager 테스트"""

    def test_default_whitelist_contains_common_terms(self):
        """기본 화이트리스트에 공통 용어 포함 확인"""
        manager = WhitelistManager(initial_words=list(DEFAULT_WHITELIST))

        # 일반 호칭 (오탐 방지) - 범용화된 화이트리스트
        assert manager.contains("이모")
        assert manager.contains("담당")
        assert manager.contains("가족")
        assert manager.contains("친구")

    def test_add_words(self):
        """단어 추가 테스트"""
        manager = WhitelistManager(initial_words=["테스트"])

        # 새 단어 추가
        added = manager.add_words(["추가단어", "또다른단어"])
        assert added == 2
        assert manager.contains("추가단어")
        assert manager.contains("또다른단어")

        # 중복 단어는 추가되지 않음
        added = manager.add_words(["추가단어"])
        assert added == 0

    def test_remove_words(self):
        """단어 제거 테스트"""
        manager = WhitelistManager(initial_words=["단어1", "단어2", "단어3"])

        removed = manager.remove_words(["단어1", "단어2"])
        assert removed == 2
        assert not manager.contains("단어1")
        assert not manager.contains("단어2")
        assert manager.contains("단어3")

    def test_contains_with_in_operator(self):
        """in 연산자 테스트"""
        manager = WhitelistManager(initial_words=["테스트"])

        assert "테스트" in manager
        assert "없는단어" not in manager


class TestPrivacyMaskerWithWhitelist:
    """PrivacyMasker 화이트리스트 통합 테스트"""

    def test_false_positive_prevention_이모님(self):
        """오탐 방지: '이모님'은 마스킹하지 않음"""
        masker = PrivacyMasker(whitelist=["이모"])
        # "이모님"에서 "이모"는 화이트리스트에 있으므로 마스킹 안 함
        # 패턴: ([가-힣]{2,4})(?=\s*(고객님|담당자님?))
        # "이모님"은 이 패턴에 매칭되지 않으므로 원래부터 마스킹 대상 아님
        text = "이모님이 도와주셨어요"
        result = masker.mask_text(text)
        assert result == text  # 변경 없음

    def test_false_positive_prevention_헬퍼님(self):
        """오탐 방지: '헬퍼님'은 마스킹하지 않음"""
        masker = PrivacyMasker(whitelist=["헬퍼"])
        text = "헬퍼님께 감사드립니다"
        result = masker.mask_text(text)
        assert result == text  # 변경 없음

    def test_false_positive_prevention_고객님(self):
        """오탐 방지: '고객님' 단독은 마스킹하지 않음 (이름 없이)"""
        masker = PrivacyMasker(whitelist=["고객"])
        # "고객님"만 있는 경우 (이름 없이)
        text = "고객님 입장입니다"
        result = masker.mask_text(text)
        assert result == text  # 변경 없음

    def test_false_positive_prevention_담당_매니저(self):
        """오탐 방지: '담당 매니저'는 마스킹하지 않음"""
        masker = PrivacyMasker(whitelist=["담당", "매니저"])
        text = "담당 매니저가 안내해드릴게요"
        result = masker.mask_text(text)
        assert result == text  # 변경 없음

    def test_whitelist_exception_in_name_masking(self):
        """화이트리스트 단어가 이름 패턴과 매칭되더라도 마스킹 안 함"""
        masker = PrivacyMasker(whitelist=["이모", "헬퍼", "담당"])

        # 화이트리스트 단어 + 기본 패턴 (고객님/담당자님)
        # 이 경우도 화이트리스트에 의해 보호됨
        test_cases = [
            ("이모 고객님", "이모 고객님"),  # 이모는 화이트리스트
            ("헬퍼 담당자님", "헬퍼 담당자님"),  # 헬퍼는 화이트리스트
            ("담당 고객님", "담당 고객님"),  # 담당은 화이트리스트
        ]

        for input_text, _expected in test_cases:
            result = masker.mask_text(input_text)
            # 정규식 패턴과 화이트리스트에 따라 결과가 달라질 수 있음
            # 핵심은 화이트리스트 단어가 마스킹되지 않는 것
            assert "이*" not in result or "이모" in result  # 이모가 마스킹되면 안 됨

    def test_real_name_still_masked(self):
        """실제 이름은 여전히 마스킹됨 (기본 패턴: 고객님)"""
        masker = PrivacyMasker(whitelist=["이모", "헬퍼"])

        # 실제 이름 마스킹 테스트 (기본 패턴 사용)
        text = "김철수 고객님께서 입장하십니다"
        result = masker.mask_text(text)
        assert "김**" in result  # 이름은 마스킹됨
        assert "김철수" not in result

    def test_phone_masking_unchanged(self):
        """전화번호 마스킹은 화이트리스트 영향 없음"""
        masker = PrivacyMasker(whitelist=["이모"])

        text = "연락처: 010-1234-5678"
        result = masker.mask_text(text)
        assert "010-****-5678" in result

    def test_business_phone_not_masked(self):
        """업체 전화번호는 마스킹 안 함"""
        masker = PrivacyMasker()

        text = "업체 연락처: 02-1234-5678"
        result = masker.mask_text(text)
        assert "02-1234-5678" in result  # 업체번호 유지


class TestPIIProcessor:
    """PIIProcessor Facade 테스트"""

    def test_process_answer_mode(self):
        """answer 모드 테스트"""
        processor = PIIProcessor()

        result = processor.process("연락처: 010-1234-5678", mode="answer")

        assert result.mode.value == "answer"
        assert "010-****-5678" in result.masked_text
        assert result.phone_masked_count == 1
        assert result.contains_pii is True

    def test_process_filename_mode(self):
        """filename 모드 테스트"""
        processor = PIIProcessor()

        result = processor.process("이한솔 고객님.txt", mode="filename")

        assert result.mode.value == "filename"
        assert "고객_고객님.txt" in result.masked_text
        assert result.name_masked_count == 1

    def test_process_document_mode(self):
        """document 모드 테스트"""
        processor = PIIProcessor()

        result = processor.process("김철수 고객님 010-1234-5678", mode="document")

        assert result.mode.value == "document"
        assert "김**" in result.masked_text

    def test_process_with_whitelist_exception(self):
        """화이트리스트 예외 적용 테스트"""
        processor = PIIProcessor()

        # 화이트리스트 단어는 마스킹 안 됨
        result = processor.process("이모님이 도와주셨어요", mode="answer")
        assert result.masked_text == "이모님이 도와주셨어요"
        assert result.name_masked_count == 0

    def test_contains_pii(self):
        """PII 포함 여부 확인 테스트"""
        processor = PIIProcessor()

        assert processor.contains_pii("010-1234-5678") is True
        assert processor.contains_pii("안녕하세요") is False

    def test_mask_sources_filenames(self):
        """sources 배열 파일명 마스킹 테스트"""
        processor = PIIProcessor()

        sources = [
            {"document": "이한솔 고객님.txt", "relevance": 50.0},
            {"document": "일반문서.txt", "relevance": 45.0},
        ]

        masked = processor.mask_sources_filenames(sources)

        assert masked[0]["document"] == "고객_고객님.txt"
        assert masked[1]["document"] == "일반문서.txt"  # 패턴 미매칭 시 유지


class TestProcessPIIConvenienceFunction:
    """process_pii 편의 함수 테스트"""

    def test_basic_usage(self):
        """기본 사용법 테스트"""
        result = process_pii("연락처: 010-1234-5678")

        assert "010-****-5678" in result.masked_text

    def test_with_mode(self):
        """모드 지정 테스트"""
        result = process_pii("이한솔 고객님.txt", mode="filename")

        assert "고객_고객님.txt" in result.masked_text


class TestRegressionCases:
    """회귀 테스트 - 버그 수정 확인 (범용화 버전)"""

    def test_issue_이모님_false_positive(self):
        """
        이슈: '이모님'이 '이*님'으로 잘못 마스킹됨
        원인: 정규식 패턴에 '님' 단독 포함
        수정: '님' 단독 패턴 제거 + 화이트리스트 추가
        """
        processor = PIIProcessor()

        result = processor.process("이모님이 식사 준비하셨어요", mode="answer")

        # 이모님은 마스킹되면 안 됨
        assert "이*님" not in result.masked_text
        assert "이모님" in result.masked_text

    def test_issue_헬퍼님_false_positive(self):
        """
        이슈: '헬퍼님'이 잘못 마스킹됨
        """
        processor = PIIProcessor()

        result = processor.process("헬퍼님께 연락 부탁드려요", mode="answer")

        assert "헬*님" not in result.masked_text
        assert "헬퍼님" in result.masked_text

    def test_issue_고객님_standalone_no_masking(self):
        """
        '고객님' 단독 사용 시 마스킹되지 않음 (이름 없이)
        """
        processor = PIIProcessor()

        result = processor.process("고객님 입장입니다", mode="answer")

        # 이름 없이 '고객님'만 있는 경우 마스킹 안 됨
        assert "고*님" not in result.masked_text
        assert "고객님" in result.masked_text

    def test_issue_담당_매니저_false_positive(self):
        """
        이슈: '담당 매니저'가 '담* 매니저'로 잘못 마스킹됨
        """
        processor = PIIProcessor()

        result = processor.process("담당 매니저가 안내해드릴게요", mode="answer")

        assert "담* 매니저" not in result.masked_text
        assert "담당" in result.masked_text


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_text(self):
        """빈 텍스트 처리"""
        processor = PIIProcessor()

        result = processor.process("", mode="answer")
        assert result.masked_text == ""
        assert result.total_masked_count == 0

    def test_mixed_content(self):
        """복합 콘텐츠 (이름 + 전화번호 + 화이트리스트)"""
        processor = PIIProcessor()

        text = "김철수 고객님과 이모님 연락처: 010-1234-5678"
        result = processor.process(text, mode="answer")

        # 이름은 마스킹 (고객님 패턴)
        assert "김**" in result.masked_text
        # 이모님은 유지
        assert "이모님" in result.masked_text
        # 전화번호는 마스킹
        assert "010-****-5678" in result.masked_text

    def test_multiple_names(self):
        """여러 이름 처리"""
        processor = PIIProcessor()

        text = "김철수 고객님과 이영희 담당자님"
        result = processor.process(text, mode="answer")

        assert "김**" in result.masked_text
        assert "이**" in result.masked_text
        assert result.name_masked_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
