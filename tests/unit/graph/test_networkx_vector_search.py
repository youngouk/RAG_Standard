
import numpy as np
import pytest

from app.modules.core.graph.models import Entity
from app.modules.core.graph.stores.networkx_store import NetworkXGraphStore


class MockEmbedder:
    async def embed_query(self, text: str):
        # 결정론적 벡터 (768차원)
        vec = np.zeros(768)
        if "삼성" in text or "SAMSUNG" in text:
            vec[0] = 1.0
        elif "애플" in text or "iPhone" in text:
            vec[0] = -1.0
        return vec.tolist()

    async def embed_documents(self, texts: list[str]):
        return [await self.embed_query(t) for t in texts]

@pytest.mark.asyncio
async def test_networkx_graph_vector_search():
    # 1. Setup
    store = NetworkXGraphStore()
    embedder = MockEmbedder()
    store.set_embedder(embedder) # 새로 구현할 메서드

    # 2. 데이터 준비
    samsung = Entity(
        id="corp_1",
        name="삼성전자",
        type="Organization",
        properties={"description": "대한민국 반도체 기업"}
    )
    apple = Entity(
        id="corp_2",
        name="애플",
        type="Organization",
        properties={"description": "미국 IT 기업"}
    )

    await store.add_entity(samsung)
    await store.add_entity(apple)

    # 3. 시나리오: 의미적 유사어 검색 ("SAMSUNG" -> "삼성전자")
    # 현재 구현은 "SAMSUNG"이 "삼성전자"에 포함되지 않으므로 실패함 (결과 0개 예상)
    # 하지만 고도화 후에는 1개가 나와야 함
    result = await store.search(query="SAMSUNG", top_k=1)

    assert len(result.entities) > 0
    assert result.entities[0].name == "삼성전자"
    # score 필드가 GraphSearchResult에 있으므로 점수 확인 가능
    assert result.score > 0.5
