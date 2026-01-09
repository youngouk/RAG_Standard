"""
User Dictionary 사용자 사전 테스트

테스트 범위:
1. 엔트리 보호 (형태소 분석 방지)
2. 엔트리 복원
3. 패턴 빌드 (긴 단어 우선)
4. 엔트리 찾기
5. 엔트리 관리 (추가/제거)
6. 비활성화 모드
"""

import pytest

from app.modules.core.retrieval.bm25.user_dictionary import UserDictionary


@pytest.mark.unit
class TestUserDictionary:
    """User Dictionary 테스트"""

    @pytest.fixture
    def dict_empty(self):
        """빈 사용자 사전"""
        return UserDictionary(custom_entries=None, use_defaults=False, enabled=True)

    @pytest.fixture
    def dict_with_entries(self):
        """엔트리가 있는 사용자 사전"""
        entries = {"복합항목명", "서울특별시", "AI모델"}
        return UserDictionary(custom_entries=entries, use_defaults=False, enabled=True)

    @pytest.fixture
    def dict_disabled(self):
        """비활성화된 사용자 사전"""
        return UserDictionary(enabled=False)

    def test_protect_entries_replaces_with_tokens(self, dict_with_entries):
        """
        엔트리를 임시 토큰으로 보호

        Given: 사용자 사전에 "복합항목명" 등록
        When: protect_entries("복합항목명을 조회합니다") 호출
        Then: "__USER_DICT_0__을 조회합니다" 반환
        """
        text = "복합항목명을 조회합니다"
        protected, restore_map = dict_with_entries.protect_entries(text)

        # 검증: 토큰으로 대체됨
        assert "__USER_DICT_0__" in protected
        assert "복합항목명" not in protected
        assert len(restore_map) == 1
        assert "__USER_DICT_0__" in restore_map
        assert restore_map["__USER_DICT_0__"] == "복합항목명"

    def test_protect_multiple_entries(self, dict_with_entries):
        """
        복수 엔트리 보호

        Given: 사용자 사전에 여러 엔트리
        When: protect_entries() 호출
        Then: 각각 다른 토큰으로 대체
        """
        text = "서울특별시 복합항목명 AI모델"
        protected, restore_map = dict_with_entries.protect_entries(text)

        # 검증: 3개 토큰 생성
        assert len(restore_map) == 3
        assert "복합항목명" not in protected
        assert "서울특별시" not in protected
        assert "AI모델" not in protected

        # 각 엔트리가 restore_map에 존재
        assert "복합항목명" in restore_map.values()
        assert "서울특별시" in restore_map.values()
        assert "AI모델" in restore_map.values()

    def test_restore_entries_reconstructs_original(self, dict_with_entries):
        """
        보호된 엔트리 복원

        Given: 보호된 텍스트와 restore_map
        When: restore_entries() 호출
        Then: 원본 텍스트 복원
        """
        original = "복합항목명을 조회합니다"
        protected, restore_map = dict_with_entries.protect_entries(original)

        # 복원
        restored = dict_with_entries.restore_entries(protected, restore_map)

        # 검증: 원본 복원
        assert restored == original

    def test_protect_and_restore_round_trip(self, dict_with_entries):
        """
        보호 → 복원 라운드 트립

        Given: 복잡한 텍스트
        When: protect → restore 연속 호출
        Then: 원본 텍스트 완전 복원
        """
        original = "서울특별시 강남구에서 복합항목명 조회 시 AI모델 사용"
        protected, restore_map = dict_with_entries.protect_entries(original)
        restored = dict_with_entries.restore_entries(protected, restore_map)

        # 검증: 완전 복원
        assert restored == original

    def test_contains(self, dict_with_entries):
        """
        엔트리 포함 여부 확인

        Given: 사용자 사전
        When: contains() 호출
        Then: 포함 여부 반환
        """
        # 검증: 엔트리 확인
        assert dict_with_entries.contains("복합항목명") is True
        assert dict_with_entries.contains("서울특별시") is True
        assert dict_with_entries.contains("존재안함") is False

    def test_find_entries(self, dict_with_entries):
        """
        텍스트에서 엔트리 찾기

        Given: 사용자 사전
        When: find_entries("서울특별시 복합항목명") 호출
        Then: ["서울특별시", "복합항목명"] 반환
        """
        text = "서울특별시 강남구 복합항목명 조회"
        found = dict_with_entries.find_entries(text)

        # 검증: 엔트리 찾기
        assert len(found) == 2
        assert "서울특별시" in found
        assert "복합항목명" in found

    def test_find_entries_no_matches(self, dict_with_entries):
        """
        매칭되는 엔트리 없음

        Given: 사용자 사전
        When: find_entries("일반 텍스트") 호출
        Then: [] 반환
        """
        text = "일반 텍스트입니다"
        found = dict_with_entries.find_entries(text)

        # 검증: 빈 리스트
        assert found == []

    def test_find_entries_empty_text(self, dict_with_entries):
        """
        빈 텍스트 처리

        Given: 사용자 사전
        When: find_entries("") 호출
        Then: [] 반환
        """
        found = dict_with_entries.find_entries("")

        # 검증: 빈 리스트
        assert found == []

    def test_add_entry(self, dict_empty):
        """
        엔트리 추가

        Given: 빈 사용자 사전
        When: add_entry("신규엔트리") 호출
        Then: 엔트리 추가됨
        """
        dict_empty.add_entry("신규엔트리")

        # 검증: 엔트리 추가됨
        assert dict_empty.contains("신규엔트리") is True
        assert len(dict_empty.entries) == 1

    def test_add_entry_rebuilds_pattern(self, dict_empty):
        """
        엔트리 추가 시 패턴 재빌드

        Given: 빈 사용자 사전
        When: add_entry() 호출
        Then: 패턴 재빌드됨
        """
        # 초기 상태: 패턴 없음
        assert dict_empty.pattern is None

        # 엔트리 추가
        dict_empty.add_entry("신규엔트리")

        # 검증: 패턴 생성됨
        assert dict_empty.pattern is not None

    def test_remove_entry(self, dict_with_entries):
        """
        엔트리 제거

        Given: 엔트리가 있는 사용자 사전
        When: remove_entry("복합항목명") 호출
        Then: 엔트리 제거됨
        """
        # 초기 상태 확인
        assert dict_with_entries.contains("복합항목명") is True

        # 엔트리 제거
        result = dict_with_entries.remove_entry("복합항목명")

        # 검증: 제거 성공
        assert result is True
        assert dict_with_entries.contains("복합항목명") is False

    def test_remove_nonexistent_entry(self, dict_with_entries):
        """
        존재하지 않는 엔트리 제거

        Given: 사용자 사전
        When: remove_entry("존재안함") 호출
        Then: False 반환
        """
        result = dict_with_entries.remove_entry("존재안함")

        # 검증: 제거 실패
        assert result is False

    def test_get_entries(self, dict_with_entries):
        """
        엔트리 세트 조회

        Given: 사용자 사전
        When: get_entries() 호출
        Then: 복사본 반환
        """
        entries = dict_with_entries.get_entries()

        # 검증: 복사본 반환 (원본 보호)
        assert isinstance(entries, set)
        assert len(entries) == 3
        assert "복합항목명" in entries

        # 복사본 수정해도 원본 영향 없음
        entries.add("테스트")
        assert "테스트" not in dict_with_entries.entries

    def test_count_property(self, dict_with_entries, dict_empty):
        """
        엔트리 개수 조회

        Given: 사용자 사전
        When: count 프로퍼티 조회
        Then: 엔트리 개수 반환
        """
        # 검증: 엔트리 개수
        assert dict_with_entries.count == 3
        assert dict_empty.count == 0

    def test_disabled_dict_returns_original(self, dict_disabled):
        """
        비활성화 사전은 원본 반환

        Given: enabled=False 사전
        When: protect_entries() 호출
        Then: 원본 그대로 반환
        """
        text = "복합항목명을 조회합니다"
        protected, restore_map = dict_disabled.protect_entries(text)

        # 검증: 원본 그대로 반환
        assert protected == text
        assert restore_map == {}

    def test_disabled_dict_no_entries_loaded(self, dict_disabled):
        """
        비활성화 사전은 엔트리 로드 안 함

        Given: enabled=False 사전
        When: 초기화
        Then: entries 세트 비어있음
        """
        # 검증: 엔트리 세트 비어있음
        assert len(dict_disabled.entries) == 0
        assert dict_disabled.count == 0
        assert dict_disabled.pattern is None

    def test_pattern_longest_first_matching(self):
        """
        긴 단어 우선 매칭

        Given: "AI", "AI모델" 엔트리
        When: protect_entries("AI모델 사용") 호출
        Then: "AI모델"이 먼저 매칭됨 ("AI"로 분리 안 됨)
        """
        entries = {"AI", "AI모델"}
        dict_long = UserDictionary(custom_entries=entries, use_defaults=False, enabled=True)

        text = "AI모델 사용"
        protected, restore_map = dict_long.protect_entries(text)

        # 검증: "AI모델" 전체가 하나의 토큰으로 보호됨
        assert len(restore_map) == 1
        assert "AI모델" in restore_map.values()

    def test_empty_restore_map(self, dict_with_entries):
        """
        빈 restore_map 복원

        Given: 사용자 사전
        When: restore_entries("원본 텍스트", {}) 호출
        Then: 원본 그대로 반환
        """
        text = "일반 텍스트"
        restored = dict_with_entries.restore_entries(text, {})

        # 검증: 원본 그대로
        assert restored == text

    def test_protect_entries_with_duplicates(self, dict_with_entries):
        """
        중복 엔트리 보호

        Given: 사용자 사전
        When: protect_entries("복합항목명과 복합항목명") 호출
        Then: 각각 다른 토큰으로 대체
        """
        text = "복합항목명과 복합항목명"
        protected, restore_map = dict_with_entries.protect_entries(text)

        # 검증: 2개 토큰 생성 (중복도 각각 보호)
        assert len(restore_map) == 2
        assert all(v == "복합항목명" for v in restore_map.values())

    def test_build_pattern_empty_entries(self, dict_empty):
        """
        빈 엔트리로 패턴 빌드

        Given: 빈 사용자 사전
        When: _build_pattern() 호출
        Then: pattern = None
        """
        dict_empty._build_pattern()

        # 검증: 패턴 없음
        assert dict_empty.pattern is None

    def test_default_entries_usage(self):
        """
        기본 엔트리 사용

        Given: use_defaults=True
        When: 초기화
        Then: 기본 엔트리 로드 (현재는 빈 세트)
        """
        dict_default = UserDictionary(use_defaults=True, enabled=True)

        # 검증: 기본 엔트리 개수 (현재 0개)
        assert dict_default.count == len(UserDictionary.DEFAULT_ENTRIES)
