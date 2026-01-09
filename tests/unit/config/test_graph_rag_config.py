"""
GraphRAG 설정 테스트
hybrid_search.auto_enable 설정 검증
"""
import pytest
import yaml


class TestGraphRagConfig:
    """GraphRAG YAML 설정 테스트"""

    @pytest.fixture
    def graph_rag_config(self):
        """graph_rag.yaml 파일 로드"""
        with open("app/config/features/graph_rag.yaml") as f:
            return yaml.safe_load(f)

    def test_hybrid_search_section_exists(self, graph_rag_config):
        """hybrid_search 섹션이 존재하는지 확인"""
        assert "graph_rag" in graph_rag_config
        assert "hybrid_search" in graph_rag_config["graph_rag"]

    def test_hybrid_search_auto_enable_exists(self, graph_rag_config):
        """auto_enable 설정이 존재하는지 확인"""
        hybrid = graph_rag_config["graph_rag"]["hybrid_search"]
        assert "auto_enable" in hybrid
        assert isinstance(hybrid["auto_enable"], bool)

    def test_hybrid_search_fallback_to_vector_exists(self, graph_rag_config):
        """fallback_to_vector 설정이 존재하는지 확인"""
        hybrid = graph_rag_config["graph_rag"]["hybrid_search"]
        assert "fallback_to_vector" in hybrid
        assert isinstance(hybrid["fallback_to_vector"], bool)

    def test_hybrid_search_default_values(self, graph_rag_config):
        """hybrid_search 기본값 확인"""
        hybrid = graph_rag_config["graph_rag"]["hybrid_search"]

        # 기존 설정
        assert hybrid.get("enabled") is True
        assert hybrid.get("vector_weight") == 0.6
        assert hybrid.get("graph_weight") == 0.4
        assert hybrid.get("rrf_k") == 60

        # 새 설정
        assert hybrid.get("auto_enable") is False  # 기본값: 비활성화 (안전)
        assert hybrid.get("fallback_to_vector") is True  # 기본값: 활성화 (안전)
