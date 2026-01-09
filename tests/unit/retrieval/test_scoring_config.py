"""
Scoring Config 테스트

설정 파일에서 scoring 섹션을 올바르게 읽어오는지 검증한다.

TDD Step 1: 이 테스트는 먼저 작성되어 FAIL해야 한다.
"""

from app.lib.config_loader import load_config


class TestScoringConfig:
    """Scoring 설정 로드 테스트"""

    def test_scoring_section_exists(self):
        """scoring 섹션이 존재해야 한다"""
        config = load_config(validate=False)
        assert "scoring" in config, "rag.yaml에 scoring 섹션이 없습니다"

    def test_default_collection_weight_disabled(self):
        """기본값: collection_weight_enabled는 False여야 한다"""
        config = load_config(validate=False)
        scoring = config.get("scoring", {})
        enabled = scoring.get("collection_weight_enabled", True)
        assert enabled is False, "기본값은 collection_weight_enabled: false 여야 합니다"

    def test_default_file_type_weight_disabled(self):
        """기본값: file_type_weight_enabled는 False여야 한다"""
        config = load_config(validate=False)
        scoring = config.get("scoring", {})
        enabled = scoring.get("file_type_weight_enabled", True)
        assert enabled is False, "기본값은 file_type_weight_enabled: false 여야 합니다"

    def test_collection_weights_default_values(self):
        """컬렉션 가중치 기본값은 모두 1.0이어야 한다"""
        config = load_config(validate=False)
        scoring = config.get("scoring", {})
        weights = scoring.get("collection_weights", {})

        for collection, weight in weights.items():
            assert weight == 1.0, f"{collection}의 기본 가중치는 1.0이어야 합니다"

    def test_file_type_weights_default_values(self):
        """파일 타입 가중치 기본값은 모두 1.0이어야 한다"""
        config = load_config(validate=False)
        scoring = config.get("scoring", {})
        weights = scoring.get("file_type_weights", {})

        for file_type, weight in weights.items():
            assert weight == 1.0, f"{file_type}의 기본 가중치는 1.0이어야 합니다"

    def test_legacy_source_boost_removed(self):
        """기존 source_boost 섹션이 제거되어야 한다"""
        config = load_config(validate=False)
        rag_config = config.get("rag", {})

        assert "source_boost" not in rag_config, \
            "source_boost는 scoring.file_type_weights로 마이그레이션되어야 합니다"

