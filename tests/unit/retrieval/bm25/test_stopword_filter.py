"""
Stopword Filter 불용어 처리 테스트

테스트 범위:
1. 기본 불용어 필터링
2. 커스텀 불용어 추가
3. 텍스트 필터링
4. 불용어 판별
5. 불용어 관리 (추가/제거)
6. 비활성화 모드
"""

import pytest

from app.modules.core.retrieval.bm25.stopwords import StopwordFilter


@pytest.mark.unit
class TestStopwordFilter:
    """Stopword Filter 테스트"""

    @pytest.fixture
    def filter_default(self):
        """기본 불용어 필터"""
        return StopwordFilter(use_defaults=True, enabled=True)

    @pytest.fixture
    def filter_custom(self):
        """커스텀 불용어 필터"""
        custom = {"추천", "후기", "리뷰", "문의"}
        return StopwordFilter(custom_stopwords=custom, use_defaults=False, enabled=True)

    @pytest.fixture
    def filter_disabled(self):
        """비활성화된 필터"""
        return StopwordFilter(enabled=False)

    def test_filter_removes_default_stopwords(self, filter_default):
        """
        기본 불용어 제거

        Given: 기본 불용어 필터
        When: filter(["있는", "맛집", "같은"]) 호출
        Then: ["맛집"] 반환 (불용어 제거)
        """
        tokens = ["있는", "맛집", "같은"]
        filtered = filter_default.filter(tokens)

        # 검증: 불용어 제거됨
        assert filtered == ["맛집"]
        assert "있는" not in filtered
        assert "같은" not in filtered

    def test_filter_preserves_valid_tokens(self, filter_default):
        """
        유효한 토큰 유지

        Given: 기본 불용어 필터
        When: filter(["강남", "맛집", "추천"]) 호출
        Then: 모든 토큰 유지 (불용어 없음)
        """
        tokens = ["강남", "맛집", "추천"]
        filtered = filter_default.filter(tokens)

        # 검증: 모든 토큰 유지
        assert filtered == ["강남", "맛집", "추천"]

    def test_filter_text_removes_stopwords(self, filter_default):
        """
        텍스트에서 불용어 제거

        Given: 기본 불용어 필터
        When: filter_text("있는 맛집 같은 곳") 호출
        Then: "맛집 곳" 반환
        """
        text = "있는 맛집 같은 곳"
        filtered = filter_default.filter_text(text)

        # 검증: 불용어 제거된 텍스트
        assert filtered == "맛집 곳"

    def test_filter_text_empty_input(self, filter_default):
        """
        빈 텍스트 처리

        Given: 기본 불용어 필터
        When: filter_text("") 호출
        Then: "" 반환
        """
        filtered = filter_default.filter_text("")

        # 검증: 빈 문자열 반환
        assert filtered == ""

    def test_custom_stopwords_only(self, filter_custom):
        """
        커스텀 불용어만 사용

        Given: 커스텀 불용어 필터 (기본 불용어 비활성화)
        When: filter(["추천", "맛집", "후기"]) 호출
        Then: ["맛집"] 반환
        """
        tokens = ["추천", "맛집", "후기"]
        filtered = filter_custom.filter(tokens)

        # 검증: 커스텀 불용어만 제거
        assert filtered == ["맛집"]
        assert "추천" not in filtered
        assert "후기" not in filtered

    def test_custom_preserves_default_stopwords(self, filter_custom):
        """
        커스텀 필터는 기본 불용어 유지

        Given: 커스텀 불용어 필터 (use_defaults=False)
        When: filter(["있는", "맛집"]) 호출
        Then: ["있는", "맛집"] 반환 (기본 불용어 "있는"도 유지)
        """
        tokens = ["있는", "맛집"]
        filtered = filter_custom.filter(tokens)

        # 검증: 기본 불용어는 제거 안 됨
        assert "있는" in filtered
        assert "맛집" in filtered

    def test_is_stopword(self, filter_default):
        """
        불용어 판별

        Given: 기본 불용어 필터
        When: is_stopword("있는") 호출
        Then: True 반환
        """
        # 검증: 불용어 판별
        assert filter_default.is_stopword("있는") is True
        assert filter_default.is_stopword("같은") is True
        assert filter_default.is_stopword("맛집") is False

    def test_add_stopword(self, filter_default):
        """
        불용어 추가

        Given: 기본 불용어 필터
        When: add_stopword("신규") 호출
        Then: "신규"가 불용어로 추가됨
        """
        filter_default.add_stopword("신규")

        # 검증: 불용어 추가됨
        assert filter_default.is_stopword("신규") is True
        assert "신규" in filter_default.stopwords

    def test_remove_stopword(self, filter_default):
        """
        불용어 제거

        Given: 기본 불용어 필터
        When: remove_stopword("있는") 호출
        Then: "있는"이 불용어에서 제거됨
        """
        # 초기 상태 확인
        assert filter_default.is_stopword("있는") is True

        # 불용어 제거
        result = filter_default.remove_stopword("있는")

        # 검증: 제거 성공
        assert result is True
        assert filter_default.is_stopword("있는") is False
        assert "있는" not in filter_default.stopwords

    def test_remove_nonexistent_stopword(self, filter_default):
        """
        존재하지 않는 불용어 제거

        Given: 기본 불용어 필터
        When: remove_stopword("존재안함") 호출
        Then: False 반환
        """
        result = filter_default.remove_stopword("존재안함")

        # 검증: 제거 실패
        assert result is False

    def test_get_stopwords(self, filter_default):
        """
        불용어 세트 조회

        Given: 기본 불용어 필터
        When: get_stopwords() 호출
        Then: 복사본 반환
        """
        stopwords = filter_default.get_stopwords()

        # 검증: 복사본 반환 (원본 보호)
        assert isinstance(stopwords, set)
        assert len(stopwords) > 0
        assert "있는" in stopwords

        # 복사본 수정해도 원본 영향 없음
        stopwords.add("테스트")
        assert "테스트" not in filter_default.stopwords

    def test_count_property(self, filter_default, filter_custom):
        """
        불용어 개수 조회

        Given: 기본/커스텀 불용어 필터
        When: count 프로퍼티 조회
        Then: 불용어 개수 반환
        """
        # 검증: 기본 불용어 개수
        assert filter_default.count == len(StopwordFilter.DEFAULT_STOPWORDS)

        # 검증: 커스텀 불용어 개수
        assert filter_custom.count == 4  # 추천, 후기, 리뷰, 문의

    def test_disabled_filter_returns_original(self, filter_disabled):
        """
        비활성화 필터는 원본 반환

        Given: enabled=False 필터
        When: filter() 호출
        Then: 원본 토큰 그대로 반환
        """
        tokens = ["있는", "맛집", "같은"]
        filtered = filter_disabled.filter(tokens)

        # 검증: 원본 그대로 반환
        assert filtered == tokens

    def test_disabled_filter_no_stopwords_loaded(self, filter_disabled):
        """
        비활성화 필터는 불용어 로드 안 함

        Given: enabled=False 필터
        When: 초기화
        Then: stopwords 세트 비어있음
        """
        # 검증: 불용어 세트 비어있음
        assert len(filter_disabled.stopwords) == 0
        assert filter_disabled.count == 0

    def test_filter_handles_empty_tokens(self, filter_default):
        """
        빈 토큰 리스트 처리

        Given: 기본 불용어 필터
        When: filter([]) 호출
        Then: [] 반환
        """
        filtered = filter_default.filter([])

        # 검증: 빈 리스트 반환
        assert filtered == []

    def test_filter_mixed_stopwords_and_valid(self, filter_default):
        """
        불용어와 유효 토큰 혼합

        Given: 기본 불용어 필터
        When: filter(["강남", "있는", "맛집", "같은", "곳"]) 호출
        Then: ["강남", "맛집", "곳"] 반환
        """
        tokens = ["강남", "있는", "맛집", "같은", "곳"]
        filtered = filter_default.filter(tokens)

        # 검증: 불용어만 제거
        assert filtered == ["강남", "맛집", "곳"]
        assert len(filtered) == 3

    def test_combined_default_and_custom(self):
        """
        기본 + 커스텀 불용어 조합

        Given: 기본 불용어 + 커스텀 불용어 {"추천", "리뷰"}
        When: filter() 호출
        Then: 기본 + 커스텀 불용어 모두 제거
        """
        custom = {"추천", "리뷰"}
        filter_combined = StopwordFilter(
            custom_stopwords=custom, use_defaults=True, enabled=True
        )

        tokens = ["있는", "강남", "맛집", "추천", "리뷰"]
        filtered = filter_combined.filter(tokens)

        # 검증: 기본 + 커스텀 불용어 모두 제거
        assert filtered == ["강남", "맛집"]
        assert "있는" not in filtered  # 기본 불용어
        assert "추천" not in filtered  # 커스텀 불용어
        assert "리뷰" not in filtered  # 커스텀 불용어
