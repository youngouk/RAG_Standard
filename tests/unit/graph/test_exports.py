"""
graph 모듈 익스포트 테스트
"""


class TestGraphModuleExports:
    """graph 모듈 익스포트 테스트"""

    def test_can_import_entity(self):
        """Entity 임포트 가능"""
        from app.modules.core.graph import Entity

        assert Entity is not None

    def test_can_import_relation(self):
        """Relation 임포트 가능"""
        from app.modules.core.graph import Relation

        assert Relation is not None

    def test_can_import_graph_search_result(self):
        """GraphSearchResult 임포트 가능"""
        from app.modules.core.graph import GraphSearchResult

        assert GraphSearchResult is not None

    def test_can_import_igraphstore(self):
        """IGraphStore 임포트 가능"""
        from app.modules.core.graph import IGraphStore

        assert IGraphStore is not None

    def test_can_import_networkx_graph_store(self):
        """NetworkXGraphStore 임포트 가능"""
        from app.modules.core.graph import NetworkXGraphStore

        assert NetworkXGraphStore is not None

    def test_can_import_graphrag_factory(self):
        """GraphRAGFactory 임포트 가능"""
        from app.modules.core.graph import GraphRAGFactory

        assert GraphRAGFactory is not None

    def test_all_exports_defined(self):
        """__all__ 정의 확인"""
        from app.modules.core import graph

        assert hasattr(graph, "__all__")
        assert "Entity" in graph.__all__
        assert "Relation" in graph.__all__
        assert "GraphSearchResult" in graph.__all__
        assert "IGraphStore" in graph.__all__
        assert "NetworkXGraphStore" in graph.__all__
        assert "GraphRAGFactory" in graph.__all__
