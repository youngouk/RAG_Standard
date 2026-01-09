"""
Synonym Manager 도메인 특화 테스트

테스트 범위:
1. CSV 로딩 (정상 로드, 파일 없음, 주석 처리)
2. 쿼리 확장 (동의어 → 표준어 변환)
3. 동의어 그룹 관리 (조회, 역방향 맵)
4. 동의어 판별
5. 통계 및 리로드
"""

import tempfile
from pathlib import Path

import pytest

from app.modules.core.retrieval.bm25.synonym_manager import SynonymManager


@pytest.mark.unit
class TestSynonymManager:
    """Synonym Manager 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 Synonym Manager 인스턴스 (사전 없음)"""
        return SynonymManager(csv_path=None, enabled=True)

    @pytest.fixture
    def csv_file(self):
        """임시 CSV 파일 생성"""
        content = """# 테스트 동의어 사전
강남,강남역,강남구,ㄱㄴ
맛집,맛집추천,맛있는집,맛있는곳
홍대,홍대입구,홍대거리
# 주석 행
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return Path(f.name)

    @pytest.fixture
    def manager_with_csv(self, csv_file):
        """CSV 파일을 로드한 Synonym Manager"""
        return SynonymManager(csv_path=str(csv_file), enabled=True)

    def test_load_synonyms_from_csv(self, csv_file):
        """
        CSV 파일에서 동의어 로드

        Given: 동의어 CSV 파일
        When: load_from_csv() 호출
        Then: 동의어 그룹 3개 생성 (주석 제외)
        """
        manager = SynonymManager(csv_path=str(csv_file), enabled=True)

        # 검증: 동의어 그룹 3개 생성 (강남, 맛집, 홍대)
        assert len(manager.synonym_groups) == 3
        assert "강남" in manager.synonym_groups
        assert "맛집" in manager.synonym_groups
        assert "홍대" in manager.synonym_groups

        # 검증: 각 그룹의 동의어 개수
        assert len(manager.synonym_groups["강남"]) == 4  # 강남, 강남역, 강남구, ㄱㄴ
        assert len(manager.synonym_groups["맛집"]) == 4  # 맛집, 맛집추천, 맛있는집, 맛있는곳
        assert len(manager.synonym_groups["홍대"]) == 3  # 홍대, 홍대입구, 홍대거리

    def test_reverse_map_construction(self, manager_with_csv):
        """
        역방향 맵 구축 검증

        Given: 동의어 사전 로드됨
        When: reverse_map 확인
        Then: 모든 동의어가 표준어로 매핑됨
        """
        # 검증: Reverse Map
        assert manager_with_csv.reverse_map["강남역"] == "강남"
        assert manager_with_csv.reverse_map["ㄱㄴ"] == "강남"
        assert manager_with_csv.reverse_map["맛집추천"] == "맛집"
        assert manager_with_csv.reverse_map["홍대입구"] == "홍대"

        # 표준어 자체도 reverse_map에 포함
        assert manager_with_csv.reverse_map["강남"] == "강남"

    def test_expand_query_replaces_synonyms(self, manager_with_csv):
        """
        쿼리 확장 (동의어 → 표준어)

        Given: 동의어 사전 로드됨
        When: expand_query("강남역 맛있는집 추천") 호출
        Then: "강남 맛집 추천" 반환
        """
        expanded = manager_with_csv.expand_query("강남역 맛있는집 추천")

        # 검증: 동의어 → 표준어 변환
        assert expanded == "강남 맛집 추천"

    def test_expand_query_handles_multiple_synonyms(self, manager_with_csv):
        """
        복수 동의어 확장

        Given: 동의어 사전 로드됨
        When: expand_query("ㄱㄴ 홍대입구 맛집추천") 호출
        Then: "강남 홍대 맛집" 반환
        """
        expanded = manager_with_csv.expand_query("ㄱㄴ 홍대입구 맛집추천")

        # 검증: 모든 동의어 변환
        assert expanded == "강남 홍대 맛집"

    def test_expand_query_preserves_unknown_words(self, manager_with_csv):
        """
        사전에 없는 단어 유지

        Given: 동의어 사전 로드됨
        When: expand_query("강남역 카페 좋은곳") 호출
        Then: "강남 카페 좋은곳" 반환 (카페, 좋은곳 유지)
        """
        expanded = manager_with_csv.expand_query("강남역 카페 좋은곳")

        # 검증: 사전에 없는 단어는 그대로 유지
        assert expanded == "강남 카페 좋은곳"

    def test_expand_query_disabled(self, csv_file):
        """
        기능 비활성화 시 쿼리 유지

        Given: enabled=False로 초기화
        When: expand_query() 호출
        Then: 원본 쿼리 반환
        """
        manager = SynonymManager(csv_path=str(csv_file), enabled=False)

        expanded = manager.expand_query("강남역 맛있는집")

        # 검증: 변환 없이 원본 그대로
        assert expanded == "강남역 맛있는집"

    def test_get_all_variants(self, manager_with_csv):
        """
        모든 변형 조회

        Given: 동의어 사전 로드됨
        When: get_all_variants("강남") 호출
        Then: 모든 동의어 반환 (강남역, 강남구, ㄱㄴ)
        """
        variants = manager_with_csv.get_all_variants("강남")

        # 검증: 변형 4개 (강남 포함)
        assert len(variants) == 4
        assert "강남" in variants
        assert "강남역" in variants
        assert "강남구" in variants
        assert "ㄱㄴ" in variants

    def test_get_all_variants_from_synonym(self, manager_with_csv):
        """
        동의어로 변형 조회

        Given: 동의어 사전 로드됨
        When: get_all_variants("강남역") 호출 (동의어로 조회)
        Then: 표준어 "강남"의 모든 변형 반환
        """
        variants = manager_with_csv.get_all_variants("강남역")

        # 검증: 표준어 "강남"의 모든 변형 반환
        assert len(variants) == 4
        assert "강남" in variants
        assert "강남역" in variants

    def test_get_all_variants_unknown_term(self, manager_with_csv):
        """
        사전에 없는 용어 조회

        Given: 동의어 사전 로드됨
        When: get_all_variants("서울역") 호출 (사전에 없음)
        Then: [서울역] 반환
        """
        variants = manager_with_csv.get_all_variants("서울역")

        # 검증: 원본만 반환
        assert variants == ["서울역"]

    def test_get_standard_form(self, manager_with_csv):
        """
        표준어 형태 반환

        Given: 동의어 사전 로드됨
        When: get_standard_form("ㄱㄴ") 호출
        Then: "강남" 반환
        """
        standard = manager_with_csv.get_standard_form("ㄱㄴ")

        # 검증: 표준어 반환
        assert standard == "강남"

    def test_get_standard_form_already_standard(self, manager_with_csv):
        """
        이미 표준어인 경우

        Given: 동의어 사전 로드됨
        When: get_standard_form("강남") 호출
        Then: "강남" 반환 (그대로)
        """
        standard = manager_with_csv.get_standard_form("강남")

        # 검증: 표준어 그대로 반환
        assert standard == "강남"

    def test_is_synonym(self, manager_with_csv):
        """
        두 용어가 동의어인지 확인

        Given: 동의어 사전 로드됨
        When: is_synonym("강남역", "ㄱㄴ") 호출
        Then: True 반환
        """
        # 검증: 동의어 확인
        assert manager_with_csv.is_synonym("강남역", "ㄱㄴ") is True
        assert manager_with_csv.is_synonym("강남", "강남역") is True

    def test_is_not_synonym(self, manager_with_csv):
        """
        동의어가 아닌 경우

        Given: 동의어 사전 로드됨
        When: is_synonym("강남", "홍대") 호출
        Then: False 반환
        """
        # 검증: 동의어 아님
        assert manager_with_csv.is_synonym("강남", "홍대") is False
        assert manager_with_csv.is_synonym("강남역", "맛집") is False

    def test_reload(self, csv_file):
        """
        동의어 사전 리로드

        Given: 동의어 사전 로드됨
        When: reload() 호출
        Then: 사전 재로드 (기존 데이터 유지)
        """
        manager = SynonymManager(csv_path=str(csv_file), enabled=True)

        # 초기 상태 확인
        initial_groups = len(manager.synonym_groups)
        initial_words = len(manager.reverse_map)

        # 리로드
        manager.reload()

        # 검증: 동일한 데이터 유지
        assert len(manager.synonym_groups) == initial_groups
        assert len(manager.reverse_map) == initial_words

    def test_stats_property(self, manager_with_csv):
        """
        통계 정보 반환

        Given: 동의어 사전 로드됨
        When: stats 프로퍼티 조회
        Then: 그룹 수, 단어 수, 평균 그룹 크기 반환
        """
        stats = manager_with_csv.stats

        # 검증: 통계 정보
        assert stats["총_그룹_수"] == 3
        assert stats["총_단어_수"] == 11  # 4 + 4 + 3
        assert stats["평균_그룹_크기"] > 0

    def test_empty_manager_stats(self, manager):
        """
        빈 사전의 통계

        Given: 동의어 사전 없음
        When: stats 프로퍼티 조회
        Then: 0으로 초기화된 통계 반환
        """
        stats = manager.stats

        # 검증: 빈 통계
        assert stats["총_그룹_수"] == 0
        assert stats["총_단어_수"] == 0
        assert stats["평균_그룹_크기"] == 0

    def test_csv_file_not_found(self):
        """
        CSV 파일이 없는 경우

        Given: 존재하지 않는 CSV 경로
        When: SynonymManager 초기화
        Then: 에러 없이 빈 사전으로 초기화
        """
        manager = SynonymManager(csv_path="/nonexistent/path.csv", enabled=True)

        # 검증: 빈 사전
        assert len(manager.synonym_groups) == 0
        assert len(manager.reverse_map) == 0

    def test_normalize_text(self, manager):
        """
        텍스트 정규화

        Given: 공백이 포함된 텍스트
        When: _normalize() 호출
        Then: 앞뒤 공백 제거, 연속 공백 정리
        """
        # 검증: 정규화 동작
        assert manager._normalize("  강남역  ") == "강남역"
        assert manager._normalize("강남  역") == "강남 역"
        assert manager._normalize("") == ""

    def test_csv_with_empty_rows(self):
        """
        빈 행이 포함된 CSV 로딩

        Given: 빈 행이 있는 CSV 파일
        When: 초기화
        Then: 빈 행 스킵하고 정상 로드
        """
        content = """강남,강남역

맛집,맛집추천
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            csv_file = Path(f.name)

        manager = SynonymManager(csv_path=str(csv_file), enabled=True)

        # 검증: 빈 행 스킵하고 2개 그룹만 로드
        assert len(manager.synonym_groups) == 2
        assert "강남" in manager.synonym_groups
        assert "맛집" in manager.synonym_groups

    def test_csv_loading_exception_handling(self):
        """
        CSV 로딩 중 예외 처리

        Given: 잘못된 인코딩 파일
        When: 초기화
        Then: 에러 로깅 후 빈 사전으로 초기화
        """
        # 존재하지 않는 파일 경로 (읽기 권한 없음 등)
        manager = SynonymManager(csv_path="/invalid/path/file.csv", enabled=True)

        # 검증: 에러 처리 후 빈 사전
        assert len(manager.synonym_groups) == 0
        assert len(manager.reverse_map) == 0
