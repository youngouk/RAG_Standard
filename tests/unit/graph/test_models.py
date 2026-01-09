"""
GraphRAG 데이터 모델 단위 테스트
TDD 방식으로 작성됨
"""
import pytest
from pydantic import ValidationError


class TestEntity:
    """Entity 데이터 모델 테스트"""

    def test_entity_creation_with_required_fields(self):
        """필수 필드로 Entity 생성"""
        from app.modules.core.graph.models import Entity

        entity = Entity(
            id="entity-001",
            name="A 업체",
            type="company",
        )
        assert entity.id == "entity-001"
        assert entity.name == "A 업체"
        assert entity.type == "company"
        assert entity.properties == {}  # 기본값

    def test_entity_creation_with_properties(self):
        """속성 포함 Entity 생성"""
        from app.modules.core.graph.models import Entity

        entity = Entity(
            id="entity-002",
            name="김 담당자",
            type="person",
            properties={"department": "영업팀", "phone": "010-1234-5678"},
        )
        assert entity.properties["department"] == "영업팀"

    def test_entity_requires_id(self):
        """Entity는 id 필수"""
        from app.modules.core.graph.models import Entity

        with pytest.raises(ValidationError):
            Entity(name="테스트", type="company")

    def test_entity_to_dict(self):
        """Entity를 dict로 변환"""
        from app.modules.core.graph.models import Entity

        entity = Entity(id="e1", name="테스트", type="company")
        d = entity.model_dump()
        assert d["id"] == "e1"
        assert d["name"] == "테스트"


class TestRelation:
    """Relation 데이터 모델 테스트"""

    def test_relation_creation(self):
        """Relation 생성"""
        from app.modules.core.graph.models import Relation

        relation = Relation(
            source_id="entity-001",
            target_id="entity-002",
            type="partnership",
        )
        assert relation.source_id == "entity-001"
        assert relation.target_id == "entity-002"
        assert relation.type == "partnership"
        assert relation.properties == {}

    def test_relation_with_weight(self):
        """가중치 포함 Relation"""
        from app.modules.core.graph.models import Relation

        relation = Relation(
            source_id="e1",
            target_id="e2",
            type="supply",
            weight=0.8,
            properties={"contract_date": "2025-01-01"},
        )
        assert relation.weight == 0.8
        assert relation.properties["contract_date"] == "2025-01-01"

    def test_relation_default_weight_is_one(self):
        """Relation 기본 가중치는 1.0"""
        from app.modules.core.graph.models import Relation

        relation = Relation(source_id="e1", target_id="e2", type="test")
        assert relation.weight == 1.0


class TestGraphSearchResult:
    """GraphSearchResult 데이터 모델 테스트"""

    def test_graph_search_result_creation(self):
        """GraphSearchResult 생성"""
        from app.modules.core.graph.models import Entity, GraphSearchResult, Relation

        entity = Entity(id="e1", name="A 업체", type="company")
        relation = Relation(source_id="e1", target_id="e2", type="partnership")

        result = GraphSearchResult(
            entities=[entity],
            relations=[relation],
            score=0.95,
        )
        assert len(result.entities) == 1
        assert len(result.relations) == 1
        assert result.score == 0.95

    def test_graph_search_result_empty(self):
        """빈 GraphSearchResult"""
        from app.modules.core.graph.models import GraphSearchResult

        result = GraphSearchResult(entities=[], relations=[], score=0.0)
        assert len(result.entities) == 0
        assert result.is_empty is True

    def test_graph_search_result_not_empty(self):
        """비어있지 않은 GraphSearchResult"""
        from app.modules.core.graph.models import Entity, GraphSearchResult

        entity = Entity(id="e1", name="테스트", type="test")
        result = GraphSearchResult(entities=[entity], relations=[], score=0.5)
        assert result.is_empty is False
