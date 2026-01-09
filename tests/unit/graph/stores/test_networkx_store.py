"""
NetworkXGraphStore 단위 테스트
인메모리 그래프 저장소 검증
"""
import pytest

from app.modules.core.graph.models import Entity, Relation


class TestNetworkXGraphStoreBasic:
    """NetworkXGraphStore 기본 CRUD 테스트"""

    @pytest.fixture
    def store(self):
        """테스트용 GraphStore 인스턴스"""
        from app.modules.core.graph.stores import NetworkXGraphStore

        return NetworkXGraphStore()

    @pytest.fixture
    def sample_entity(self):
        """샘플 엔티티"""
        return Entity(
            id="company-001",
            name="A 업체",
            type="company",
            properties={"location": "서울"},
        )

    @pytest.fixture
    def sample_relation(self):
        """샘플 관계"""
        return Relation(
            source_id="company-001",
            target_id="company-002",
            type="partnership",
            weight=0.9,
        )

    @pytest.mark.asyncio
    async def test_add_entity(self, store, sample_entity):
        """엔티티 추가"""
        await store.add_entity(sample_entity)

        retrieved = await store.get_entity("company-001")
        assert retrieved is not None
        assert retrieved.name == "A 업체"
        assert retrieved.type == "company"

    @pytest.mark.asyncio
    async def test_add_entity_duplicate_updates(self, store, sample_entity):
        """중복 엔티티 추가 시 업데이트"""
        await store.add_entity(sample_entity)

        # 같은 ID로 다른 이름의 엔티티 추가
        updated_entity = Entity(
            id="company-001",
            name="A 업체 (수정)",
            type="company",
        )
        await store.add_entity(updated_entity)

        retrieved = await store.get_entity("company-001")
        assert retrieved.name == "A 업체 (수정)"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, store):
        """존재하지 않는 엔티티 조회"""
        retrieved = await store.get_entity("non-existent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_add_relation(self, store, sample_relation):
        """관계 추가"""
        # 먼저 엔티티 추가
        await store.add_entity(Entity(id="company-001", name="A", type="company"))
        await store.add_entity(Entity(id="company-002", name="B", type="company"))

        # 관계 추가
        await store.add_relation(sample_relation)

        stats = store.get_stats()
        assert stats["edge_count"] == 1

    @pytest.mark.asyncio
    async def test_add_relation_creates_missing_entities(self, store, sample_relation):
        """관계 추가 시 없는 엔티티는 자동 생성"""
        # 엔티티 없이 관계만 추가
        await store.add_relation(sample_relation)

        # 엔티티가 자동 생성되었는지 확인
        entity1 = await store.get_entity("company-001")
        entity2 = await store.get_entity("company-002")

        assert entity1 is not None
        assert entity2 is not None

    @pytest.mark.asyncio
    async def test_clear(self, store, sample_entity):
        """그래프 전체 삭제"""
        await store.add_entity(sample_entity)
        await store.clear()

        stats = store.get_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0

    def test_get_stats_empty(self, store):
        """빈 그래프 통계"""
        stats = store.get_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, store):
        """데이터 있는 그래프 통계"""
        await store.add_entity(Entity(id="e1", name="A", type="company"))
        await store.add_entity(Entity(id="e2", name="B", type="company"))
        await store.add_relation(Relation(source_id="e1", target_id="e2", type="partnership"))

        stats = store.get_stats()
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1


class TestNetworkXGraphStoreNeighbors:
    """NetworkXGraphStore 이웃 탐색 테스트"""

    @pytest.fixture
    def store_with_data(self):
        """데이터가 있는 GraphStore"""
        from app.modules.core.graph.stores import NetworkXGraphStore

        return NetworkXGraphStore()

    @pytest.mark.asyncio
    async def test_get_neighbors_direct(self, store_with_data):
        """직접 이웃 조회 (depth=1)"""
        store = store_with_data

        # A -- partnership --> B
        # A -- supply --> C
        await store.add_entity(Entity(id="A", name="A업체", type="company"))
        await store.add_entity(Entity(id="B", name="B업체", type="company"))
        await store.add_entity(Entity(id="C", name="C업체", type="company"))
        await store.add_relation(Relation(source_id="A", target_id="B", type="partnership"))
        await store.add_relation(Relation(source_id="A", target_id="C", type="supply"))

        result = await store.get_neighbors("A", max_depth=1)

        assert len(result.entities) == 2  # B, C
        assert len(result.relations) == 2

    @pytest.mark.asyncio
    async def test_get_neighbors_with_relation_filter(self, store_with_data):
        """관계 타입 필터링된 이웃 조회"""
        store = store_with_data

        await store.add_entity(Entity(id="A", name="A업체", type="company"))
        await store.add_entity(Entity(id="B", name="B업체", type="company"))
        await store.add_entity(Entity(id="C", name="C업체", type="company"))
        await store.add_relation(Relation(source_id="A", target_id="B", type="partnership"))
        await store.add_relation(Relation(source_id="A", target_id="C", type="supply"))

        # partnership만 필터링
        result = await store.get_neighbors("A", relation_types=["partnership"])

        assert len(result.entities) == 1
        assert result.entities[0].id == "B"

    @pytest.mark.asyncio
    async def test_get_neighbors_two_hop(self, store_with_data):
        """2-hop 이웃 조회 (depth=2)"""
        store = store_with_data

        # A --> B --> C
        await store.add_entity(Entity(id="A", name="A", type="company"))
        await store.add_entity(Entity(id="B", name="B", type="company"))
        await store.add_entity(Entity(id="C", name="C", type="company"))
        await store.add_relation(Relation(source_id="A", target_id="B", type="partner"))
        await store.add_relation(Relation(source_id="B", target_id="C", type="partner"))

        result = await store.get_neighbors("A", max_depth=2)

        # B (1-hop), C (2-hop)
        assert len(result.entities) == 2

    @pytest.mark.asyncio
    async def test_get_neighbors_not_found(self, store_with_data):
        """존재하지 않는 엔티티의 이웃 조회"""
        result = await store_with_data.get_neighbors("non-existent")

        assert result.is_empty is True


class TestNetworkXGraphStoreSearch:
    """NetworkXGraphStore 검색 테스트"""

    @pytest.fixture
    def store(self):
        """테스트용 GraphStore 인스턴스"""
        from app.modules.core.graph.stores import NetworkXGraphStore

        return NetworkXGraphStore()

    @pytest.mark.asyncio
    async def test_search_by_name(self, store):
        """이름으로 검색"""
        await store.add_entity(Entity(id="e1", name="A 업체", type="company"))
        await store.add_entity(Entity(id="e2", name="B 업체", type="company"))
        await store.add_entity(Entity(id="e3", name="김 담당자", type="person"))

        result = await store.search("업체")

        assert len(result.entities) == 2

    @pytest.mark.asyncio
    async def test_search_with_type_filter(self, store):
        """타입으로 필터링된 검색"""
        await store.add_entity(Entity(id="e1", name="A 업체", type="company"))
        await store.add_entity(Entity(id="e2", name="B 업체", type="person"))

        result = await store.search("업체", entity_types=["company"])

        assert len(result.entities) == 1
        assert result.entities[0].id == "e1"

    @pytest.mark.asyncio
    async def test_search_no_results(self, store):
        """검색 결과 없음"""
        await store.add_entity(Entity(id="e1", name="A 업체", type="company"))

        result = await store.search("존재하지않는")

        assert result.is_empty is True
