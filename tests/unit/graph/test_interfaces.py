"""
GraphRAG 인터페이스 단위 테스트
Protocol 기반 인터페이스 검증
"""
from typing import Protocol


class TestIGraphStoreInterface:
    """IGraphStore 인터페이스 테스트"""

    def test_igraphstore_is_protocol(self):
        """IGraphStore가 Protocol인지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert issubclass(type(IGraphStore), type(Protocol))

    def test_igraphstore_is_runtime_checkable(self):
        """IGraphStore가 runtime_checkable인지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        # runtime_checkable이면 isinstance 체크 가능
        assert hasattr(IGraphStore, "__protocol_attrs__") or hasattr(
            IGraphStore, "_is_runtime_protocol"
        )

    def test_igraphstore_has_add_entity_method(self):
        """IGraphStore에 add_entity 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "add_entity")

    def test_igraphstore_has_add_relation_method(self):
        """IGraphStore에 add_relation 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "add_relation")

    def test_igraphstore_has_search_method(self):
        """IGraphStore에 search 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "search")

    def test_igraphstore_has_get_neighbors_method(self):
        """IGraphStore에 get_neighbors 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "get_neighbors")

    def test_igraphstore_has_get_entity_method(self):
        """IGraphStore에 get_entity 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "get_entity")

    def test_igraphstore_has_clear_method(self):
        """IGraphStore에 clear 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IGraphStore

        assert hasattr(IGraphStore, "clear")


class TestIEntityExtractorInterface:
    """IEntityExtractor 인터페이스 테스트"""

    def test_ientityextractor_is_protocol(self):
        """IEntityExtractor가 Protocol인지 확인"""
        from app.modules.core.graph.interfaces import IEntityExtractor

        assert issubclass(type(IEntityExtractor), type(Protocol))

    def test_ientityextractor_has_extract_method(self):
        """IEntityExtractor에 extract 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IEntityExtractor

        assert hasattr(IEntityExtractor, "extract")


class TestIRelationExtractorInterface:
    """IRelationExtractor 인터페이스 테스트"""

    def test_irelationextractor_is_protocol(self):
        """IRelationExtractor가 Protocol인지 확인"""
        from app.modules.core.graph.interfaces import IRelationExtractor

        assert issubclass(type(IRelationExtractor), type(Protocol))

    def test_irelationextractor_has_extract_method(self):
        """IRelationExtractor에 extract 메서드가 있는지 확인"""
        from app.modules.core.graph.interfaces import IRelationExtractor

        assert hasattr(IRelationExtractor, "extract")
