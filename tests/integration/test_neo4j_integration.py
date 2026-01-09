"""
Neo4j GraphStore 통합 테스트

실제 Neo4j 인스턴스와 연결하여 CRUD 및 검색 기능을 검증합니다.

주의:
- 로컬에서 실행 시: docker-compose -f docker-compose.neo4j.yml up -d
- CI에서는 services로 Neo4j 컨테이너 자동 시작
"""
import os

import pytest

from app.modules.core.graph.interfaces import Entity, Relation

# Neo4j 환경이 없으면 스킵
pytestmark = pytest.mark.skipif(
    not os.getenv("NEO4J_URI") and not os.path.exists("/.dockerenv"),
    reason="Neo4j 환경이 설정되지 않음 (NEO4J_URI 또는 Docker 필요)"
)


class TestNeo4jIntegrationCRUD:
    """Neo4j CRUD 통합 테스트"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_add_and_get_entity(self, neo4j_store):
        """
        엔티티 추가 및 조회

        Given: Neo4j 연결됨
        When: 엔티티 추가 후 조회
        Then: 동일한 엔티티 반환
        """
        # Given: 엔티티 생성
        entity = Entity(
            id="test-e1",
            name="테스트 업체",
            type="company",
            properties={"location": "강남"}
        )

        # When: 추가 및 조회
        await neo4j_store.add_entity(entity)
        retrieved = await neo4j_store.get_entity("test-e1")

        # Then: 동일한 엔티티
        assert retrieved is not None
        assert retrieved.id == "test-e1"
        assert retrieved.name == "테스트 업체"
        assert retrieved.type == "company"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_add_relation(self, neo4j_store):
        """
        관계 추가

        Given: 두 엔티티 존재
        When: 관계 추가
        Then: 이웃 탐색으로 확인 가능
        """
        # Given: 엔티티 추가
        await neo4j_store.add_entity(Entity(id="A", name="A업체", type="company"))
        await neo4j_store.add_entity(Entity(id="B", name="B업체", type="company"))

        # When: 관계 추가
        await neo4j_store.add_relation(
            Relation(source_id="A", target_id="B", type="partnership", weight=0.9)
        )

        # Then: 이웃으로 확인
        neighbors = await neo4j_store.get_neighbors("A")
        assert len(neighbors.entities) == 1
        assert neighbors.entities[0].id == "B"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_entities(self, neo4j_store):
        """
        엔티티 검색

        Given: 여러 엔티티 저장
        When: 키워드 검색
        Then: 일치하는 엔티티 반환
        """
        # Given: 엔티티 추가
        await neo4j_store.add_entity(Entity(id="c1", name="삼성전자", type="company"))
        await neo4j_store.add_entity(Entity(id="c2", name="LG전자", type="company"))
        await neo4j_store.add_entity(Entity(id="c3", name="현대자동차", type="company"))

        # When: "전자" 검색
        result = await neo4j_store.search("전자")

        # Then: 2개 엔티티 반환
        assert len(result.entities) == 2
        names = {e.name for e in result.entities}
        assert "삼성전자" in names
        assert "LG전자" in names


class TestNeo4jIntegrationHealth:
    """Neo4j 헬스체크 통합 테스트"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_is_healthy(self, neo4j_store):
        """
        헬스체크 성공

        Given: Neo4j 연결됨
        When: is_healthy() 호출
        Then: True 반환
        """
        result = await neo4j_store.is_healthy()
        assert result is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_details(self, neo4j_store):
        """
        상세 헬스체크

        Given: Neo4j 연결됨
        When: health_check() 호출
        Then: 연결 정보 반환
        """
        result = await neo4j_store.health_check()

        assert result["connected"] is True
        assert "response_time_ms" in result
        assert result["response_time_ms"] > 0


class TestNeo4jIntegrationTransaction:
    """Neo4j 트랜잭션 통합 테스트"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_commit(self, neo4j_store):
        """
        트랜잭션 커밋

        Given: 트랜잭션 시작
        When: 작업 후 정상 종료
        Then: 데이터 저장됨
        """
        # When: 트랜잭션 내에서 작업
        async with neo4j_store.transaction() as tx:
            await tx.run(
                "MERGE (e:Entity {id: $id}) SET e.name = $name",
                id="tx-test-1",
                name="트랜잭션 테스트"
            )

        # Then: 데이터 조회 가능
        entity = await neo4j_store.get_entity("tx-test-1")
        assert entity is not None
        assert entity.name == "트랜잭션 테스트"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, neo4j_store):
        """
        트랜잭션 롤백

        Given: 트랜잭션 시작
        When: 예외 발생
        Then: 데이터 롤백됨
        """
        # When: 예외 발생
        with pytest.raises(ValueError):
            async with neo4j_store.transaction() as tx:
                await tx.run(
                    "MERGE (e:Entity {id: $id}) SET e.name = $name",
                    id="tx-rollback-1",
                    name="롤백 테스트"
                )
                raise ValueError("의도적 롤백")

        # Then: 데이터 없음
        entity = await neo4j_store.get_entity("tx-rollback-1")
        assert entity is None


class TestNeo4jIntegrationMultiHop:
    """Neo4j 멀티홉 탐색 통합 테스트"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_neighbors_depth_2(self, neo4j_store):
        """
        2-hop 이웃 탐색

        Given: A → B → C 체인 구조
        When: depth=2로 탐색
        Then: B, C 모두 반환
        """
        # Given: 체인 구조
        await neo4j_store.add_entity(Entity(id="A", name="A업체", type="company"))
        await neo4j_store.add_entity(Entity(id="B", name="B업체", type="company"))
        await neo4j_store.add_entity(Entity(id="C", name="C업체", type="company"))

        await neo4j_store.add_relation(Relation(source_id="A", target_id="B", type="partner"))
        await neo4j_store.add_relation(Relation(source_id="B", target_id="C", type="partner"))

        # When: 2-hop 탐색
        result = await neo4j_store.get_neighbors("A", max_depth=2)

        # Then: B, C 모두 반환
        assert len(result.entities) == 2
        ids = {e.id for e in result.entities}
        assert "B" in ids
        assert "C" in ids

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_neighbors_with_relation_filter(self, neo4j_store):
        """
        관계 타입 필터링 탐색

        Given: 여러 관계 타입
        When: 특정 타입으로 필터링
        Then: 해당 관계만 반환
        """
        # Given: 엔티티와 다양한 관계
        await neo4j_store.add_entity(Entity(id="X", name="X업체", type="company"))
        await neo4j_store.add_entity(Entity(id="Y", name="Y업체", type="company"))
        await neo4j_store.add_entity(Entity(id="Z", name="서울", type="location"))

        await neo4j_store.add_relation(Relation(source_id="X", target_id="Y", type="partnership"))
        await neo4j_store.add_relation(Relation(source_id="X", target_id="Z", type="located_in"))

        # When: partnership만 필터링
        result = await neo4j_store.get_neighbors("X", relation_types=["partnership"])

        # Then: Y만 반환
        assert len(result.entities) == 1
        assert result.entities[0].id == "Y"
