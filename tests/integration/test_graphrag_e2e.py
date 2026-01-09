# tests/integration/test_graphrag_e2e.py
"""
GraphRAG E2E 통합 테스트

전체 파이프라인을 검증합니다:
1. 텍스트 → 엔티티 추출 → 관계 추출 → 그래프 저장
2. 그래프 검색 → 결과 반환
3. 이웃 노드 탐색 → 결과 반환

주의: LLM 호출은 Mock 처리하여 API 비용 발생 방지
주의: 실제 NetworkXGraphStore 사용
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.graph import (
    Entity,
    GraphRAGFactory,
    KnowledgeGraphBuilder,
    LLMEntityExtractor,
    LLMRelationExtractor,
    NetworkXGraphStore,
    Relation,
)


class TestGraphRAGFullPipeline:
    """GraphRAG 전체 파이프라인 E2E 테스트"""

    @pytest.fixture
    def mock_llm_client_for_entities(self):
        """
        엔티티 추출용 LLM 클라이언트 Mock

        반환값: A 업체, B 업체, 서울 (3개 엔티티)
        """
        client = MagicMock()
        client.generate = AsyncMock(
            return_value="""[
    {"name": "A 업체", "type": "company"},
    {"name": "B 업체", "type": "company"},
    {"name": "서울", "type": "location"}
]"""
        )
        return client

    @pytest.fixture
    def mock_llm_client_for_relations(self):
        """
        관계 추출용 LLM 클라이언트 Mock

        반환값: A 업체 ↔ B 업체 (partnership), A 업체 → 서울 (located_in)
        """
        client = MagicMock()
        client.generate = AsyncMock(
            return_value="""[
    {"source": "A 업체", "target": "B 업체", "type": "partnership", "weight": 0.9},
    {"source": "A 업체", "target": "서울", "type": "located_in", "weight": 1.0}
]"""
        )
        return client

    @pytest.fixture
    def mock_llm_client_combined(self):
        """
        엔티티 + 관계 추출 통합 LLM 클라이언트 Mock

        두 번 호출됨: 첫 번째는 엔티티, 두 번째는 관계
        """
        client = MagicMock()
        # 첫 번째 호출: 엔티티 추출
        # 두 번째 호출: 관계 추출
        client.generate = AsyncMock(
            side_effect=[
                """[
    {"name": "A 업체", "type": "company"},
    {"name": "B 업체", "type": "company"},
    {"name": "서울", "type": "location"}
]""",
                """[
    {"source": "A 업체", "target": "B 업체", "type": "partnership", "weight": 0.9},
    {"source": "A 업체", "target": "서울", "type": "located_in", "weight": 1.0}
]""",
            ]
        )
        return client

    @pytest.fixture
    def graph_store(self):
        """
        실제 NetworkXGraphStore 인스턴스

        테스트마다 새 인스턴스 생성 (격리)
        """
        return NetworkXGraphStore()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_text_to_graph(
        self, mock_llm_client_combined, graph_store
    ):
        """
        전체 파이프라인 테스트: 텍스트 → 그래프 저장

        Given: 텍스트와 Mock LLM 클라이언트
        When: KnowledgeGraphBuilder.build() 실행
        Then: 그래프에 엔티티와 관계가 저장됨
        """
        # Given: 컴포넌트 생성
        text = "A 업체와 B 업체가 제휴를 맺었다. A 업체는 서울에 위치해 있다."
        entity_extractor = LLMEntityExtractor(llm_client=mock_llm_client_combined)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm_client_combined)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )

        # When: 파이프라인 실행
        result = await builder.build(text)

        # Then: 결과 검증
        assert result["entities_count"] == 3, "3개 엔티티가 추출되어야 함"
        assert result["relations_count"] == 2, "2개 관계가 추출되어야 함"

        # 그래프 상태 검증
        stats = graph_store.get_stats()
        assert stats["node_count"] == 3, "그래프에 3개 노드가 있어야 함"
        assert stats["edge_count"] == 2, "그래프에 2개 엣지가 있어야 함"

        # LLM 호출 횟수 검증 (엔티티 1회 + 관계 1회)
        assert mock_llm_client_combined.generate.call_count == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_graph_search_after_build(
        self, mock_llm_client_combined, graph_store
    ):
        """
        그래프 검색 통합 테스트

        Given: 그래프가 빌드된 상태
        When: search() 실행
        Then: 일치하는 엔티티 반환
        """
        # Given: 그래프 빌드
        text = "A 업체와 B 업체가 제휴를 맺었다."
        entity_extractor = LLMEntityExtractor(llm_client=mock_llm_client_combined)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm_client_combined)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )
        await builder.build(text)

        # When: 검색 실행
        result = await graph_store.search("업체")

        # Then: 검색 결과 검증
        assert len(result.entities) == 2, "'업체' 키워드로 2개 엔티티 검색됨"

        entity_names = {e.name for e in result.entities}
        assert "A 업체" in entity_names
        assert "B 업체" in entity_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_neighbors_exploration_after_build(
        self, mock_llm_client_combined, graph_store
    ):
        """
        이웃 노드 탐색 통합 테스트

        Given: 그래프가 빌드된 상태
        When: get_neighbors() 실행
        Then: 연결된 이웃 엔티티와 관계 반환
        """
        # Given: 그래프 빌드
        text = "A 업체와 B 업체가 제휴를 맺었다. A 업체는 서울에 위치해 있다."
        entity_extractor = LLMEntityExtractor(llm_client=mock_llm_client_combined)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm_client_combined)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )
        await builder.build(text)

        # 먼저 A 업체 엔티티 ID 찾기
        search_result = await graph_store.search("A 업체")
        assert len(search_result.entities) > 0, "A 업체 엔티티가 있어야 함"

        a_entity_id = search_result.entities[0].id

        # When: 이웃 탐색 (depth=1)
        neighbors = await graph_store.get_neighbors(a_entity_id, max_depth=1)

        # Then: 이웃 결과 검증
        assert not neighbors.is_empty, "이웃이 있어야 함"
        assert len(neighbors.entities) == 2, "A 업체의 1-hop 이웃은 2개 (B 업체, 서울)"
        assert len(neighbors.relations) == 2, "2개 관계가 있어야 함"

        # 관계 타입 검증
        relation_types = {r.type for r in neighbors.relations}
        assert "partnership" in relation_types
        assert "located_in" in relation_types

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_build_from_multiple_documents(
        self, mock_llm_client_combined, graph_store
    ):
        """
        여러 문서에서 그래프 빌드 테스트

        Given: 여러 문서
        When: build_from_documents() 실행
        Then: 모든 문서가 처리되어 그래프에 저장됨
        """
        # Given: 문서 리스트
        documents = [
            {"content": "A 업체와 B 업체가 제휴를 맺었다.", "metadata": {"id": "doc1"}},
            {"content": "C 업체가 D 업체를 인수했다.", "metadata": {"id": "doc2"}},
        ]

        # 두 문서 각각에 대해 LLM 호출 (엔티티 + 관계)
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            side_effect=[
                # doc1 엔티티
                '[{"name": "A 업체", "type": "company"}, {"name": "B 업체", "type": "company"}]',
                # doc1 관계
                '[{"source": "A 업체", "target": "B 업체", "type": "partnership", "weight": 0.9}]',
                # doc2 엔티티
                '[{"name": "C 업체", "type": "company"}, {"name": "D 업체", "type": "company"}]',
                # doc2 관계
                '[{"source": "C 업체", "target": "D 업체", "type": "owns", "weight": 1.0}]',
            ]
        )

        entity_extractor = LLMEntityExtractor(llm_client=mock_llm)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )

        # When: 문서 빌드
        result = await builder.build_from_documents(documents)

        # Then: 결과 검증
        assert result["documents_processed"] == 2
        assert result["total_entities"] == 4
        assert result["total_relations"] == 2

        # 그래프 상태 검증
        stats = graph_store.get_stats()
        assert stats["node_count"] == 4, "총 4개 엔티티"
        assert stats["edge_count"] == 2, "총 2개 관계"


class TestGraphRAGSearchIntegration:
    """GraphRAG 검색 통합 테스트"""

    @pytest.fixture
    def populated_graph_store(self):
        """
        데이터가 이미 저장된 GraphStore

        직접 엔티티/관계 추가하여 LLM Mock 없이 검색 테스트
        """
        store = NetworkXGraphStore()
        return store

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_by_entity_name(self, populated_graph_store):
        """
        엔티티 이름으로 검색

        Given: 그래프에 여러 엔티티 저장
        When: 이름 키워드로 검색
        Then: 일치하는 엔티티 반환
        """
        store = populated_graph_store

        # Given: 엔티티 추가
        await store.add_entity(Entity(id="e1", name="삼성전자", type="company"))
        await store.add_entity(Entity(id="e2", name="LG전자", type="company"))
        await store.add_entity(Entity(id="e3", name="현대자동차", type="company"))
        await store.add_entity(Entity(id="p1", name="이재용", type="person"))

        # When: "전자" 키워드 검색
        result = await store.search("전자")

        # Then: 삼성전자, LG전자 반환
        assert len(result.entities) == 2
        names = {e.name for e in result.entities}
        assert "삼성전자" in names
        assert "LG전자" in names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_with_type_filter(self, populated_graph_store):
        """
        엔티티 타입 필터링 검색

        Given: 여러 타입의 엔티티
        When: 타입 필터로 검색
        Then: 해당 타입만 반환
        """
        store = populated_graph_store

        # Given: 데이터 저장
        await store.add_entity(Entity(id="c1", name="A 식당", type="company"))
        await store.add_entity(Entity(id="l1", name="강남 맛집", type="location"))
        await store.add_entity(Entity(id="c2", name="B 식당", type="company"))

        # When: 검색 수행
        result = await store.search("식당", entity_types=["company"])

        # Then: company 타입만 반환
        assert len(result.entities) == 2
        for entity in result.entities:
            assert entity.type == "company"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_neighbors_with_relation_type_filter(self, populated_graph_store):
        """
        관계 타입 필터링 이웃 탐색

        Given: 여러 관계 타입으로 연결된 엔티티
        When: 특정 관계 타입으로 필터링하여 탐색
        Then: 해당 관계만 반환
        """
        store = populated_graph_store

        # Given: 엔티티와 관계 추가
        await store.add_entity(Entity(id="A", name="A업체", type="company"))
        await store.add_entity(Entity(id="B", name="B업체", type="company"))
        await store.add_entity(Entity(id="C", name="C업체", type="company"))
        await store.add_entity(Entity(id="L", name="서울", type="location"))

        await store.add_relation(Relation(source_id="A", target_id="B", type="partnership"))
        await store.add_relation(Relation(source_id="A", target_id="C", type="supplies"))
        await store.add_relation(Relation(source_id="A", target_id="L", type="located_in"))

        # When: partnership 관계만 탐색
        result = await store.get_neighbors("A", relation_types=["partnership"])

        # Then: B업체만 반환
        assert len(result.entities) == 1
        assert result.entities[0].id == "B"
        assert result.relations[0].type == "partnership"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_hop_neighbors(self, populated_graph_store):
        """
        멀티홉 이웃 탐색 (2-hop)

        Given: A → B → C 체인 구조
        When: depth=2로 탐색
        Then: B와 C 모두 반환
        """
        store = populated_graph_store

        # Given: 체인 구조 (A → B → C)
        await store.add_entity(Entity(id="A", name="A업체", type="company"))
        await store.add_entity(Entity(id="B", name="B업체", type="company"))
        await store.add_entity(Entity(id="C", name="C업체", type="company"))

        await store.add_relation(Relation(source_id="A", target_id="B", type="partner"))
        await store.add_relation(Relation(source_id="B", target_id="C", type="partner"))

        # When: 2-hop 탐색
        result = await store.get_neighbors("A", max_depth=2)

        # Then: B (1-hop), C (2-hop) 모두 반환
        assert len(result.entities) == 2
        ids = {e.id for e in result.entities}
        assert "B" in ids
        assert "C" in ids


class TestGraphRAGFactoryIntegration:
    """GraphRAGFactory 통합 테스트"""

    @pytest.mark.integration
    def test_factory_creates_networkx_store(self):
        """
        Factory가 NetworkXGraphStore를 생성하는지 테스트

        Given: networkx provider 설정
        When: GraphRAGFactory.create() 호출
        Then: NetworkXGraphStore 인스턴스 반환
        """
        # Given: 설정
        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "networkx",
            }
        }

        # When: 팩토리 호출
        store = GraphRAGFactory.create(config)

        # Then: NetworkXGraphStore 인스턴스
        assert isinstance(store, NetworkXGraphStore)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_factory_store_operations(self):
        """
        Factory로 생성한 store가 정상 동작하는지 테스트

        Given: Factory로 생성한 store
        When: CRUD 작업 수행
        Then: 정상 동작
        """
        # Given: 팩토리로 store 생성
        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "networkx",
            }
        }
        store = GraphRAGFactory.create(config)

        # When: 엔티티 추가
        entity = Entity(id="test-1", name="테스트 업체", type="company")
        await store.add_entity(entity)

        # Then: 조회 가능
        retrieved = await store.get_entity("test-1")
        assert retrieved is not None
        assert retrieved.name == "테스트 업체"

    @pytest.mark.integration
    def test_factory_get_supported_stores(self):
        """
        지원되는 store 목록 조회

        When: get_supported_stores() 호출
        Then: networkx 포함된 리스트 반환
        """
        # When
        stores = GraphRAGFactory.get_supported_stores()

        # Then
        assert "networkx" in stores


class TestGraphRAGErrorHandling:
    """GraphRAG 오류 처리 통합 테스트"""

    @pytest.fixture
    def graph_store(self):
        """테스트용 GraphStore"""
        return NetworkXGraphStore()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_llm_failure_graceful_degradation(self, graph_store):
        """
        LLM 오류 시 graceful degradation

        Given: LLM이 오류를 발생시키는 상황
        When: 파이프라인 실행
        Then: 오류 전파 없이 빈 결과 반환
        """
        # Given: 오류 발생 LLM Mock
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("API Error"))

        entity_extractor = LLMEntityExtractor(llm_client=mock_llm)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )

        # When: 파이프라인 실행 (오류 발생해도 예외 전파되지 않음)
        result = await builder.build("테스트 텍스트")

        # Then: 빈 결과 반환 (graceful degradation)
        assert result["entities_count"] == 0
        assert result["relations_count"] == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_json_graceful_degradation(self, graph_store):
        """
        잘못된 JSON 응답 시 graceful degradation

        Given: LLM이 잘못된 JSON을 반환
        When: 파이프라인 실행
        Then: 오류 전파 없이 빈 결과 반환
        """
        # Given: 잘못된 JSON 반환 LLM Mock
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="잘못된 JSON 응답")

        entity_extractor = LLMEntityExtractor(llm_client=mock_llm)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )

        # When
        result = await builder.build("테스트 텍스트")

        # Then
        assert result["entities_count"] == 0
        assert result["relations_count"] == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_text_handling(self, graph_store):
        """
        빈 텍스트 처리

        Given: 빈 텍스트
        When: 파이프라인 실행
        Then: LLM 호출 없이 빈 결과 반환
        """
        # Given: 정상 LLM (호출되면 안 됨)
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="[]")

        entity_extractor = LLMEntityExtractor(llm_client=mock_llm)
        relation_extractor = LLMRelationExtractor(llm_client=mock_llm)

        builder = KnowledgeGraphBuilder(
            graph_store=graph_store,
            entity_extractor=entity_extractor,
            relation_extractor=relation_extractor,
        )

        # When: 빈 텍스트로 빌드
        result = await builder.build("")

        # Then: LLM 호출되지 않음
        assert result["entities_count"] == 0
        assert mock_llm.generate.call_count == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_nonexistent_entity(self, graph_store):
        """
        존재하지 않는 엔티티 검색

        Given: 빈 그래프
        When: 검색 실행
        Then: is_empty=True 결과 반환
        """
        # Given: 빈 그래프 (아무것도 추가 안 함)

        # When: 검색
        result = await graph_store.search("존재하지않는")

        # Then: 빈 결과
        assert result.is_empty is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_neighbors_nonexistent_entity(self, graph_store):
        """
        존재하지 않는 엔티티의 이웃 탐색

        Given: 빈 그래프
        When: get_neighbors() 호출
        Then: is_empty=True 결과 반환
        """
        # Given: 빈 그래프

        # When: 이웃 탐색
        result = await graph_store.get_neighbors("non-existent-id")

        # Then: 빈 결과
        assert result.is_empty is True
