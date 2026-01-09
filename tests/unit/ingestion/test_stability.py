"""
Ingestion System Stability and Resilience Test

병렬 처리, 재시도 로직, 개별 실패 복구 등 시스템의 안정성을 검증합니다.
"""
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.modules.ingestion.connectors.sitemap import SitemapConnector
from app.modules.ingestion.interfaces import StandardDocument
from app.modules.ingestion.service import IngestionService


@pytest.mark.asyncio
@respx.mock
async def test_connector_retry_on_network_error():
    """네트워크 에러 발생 시 지정된 횟수만큼 재시도하는지 확인"""
    url = "https://example.com/sitemap.xml"
    page_url = "https://example.com/page1"

    # Sitemap은 성공, Page fetch는 2번 실패 후 3번째 성공 시나리오
    respx.get(url).mock(return_value=httpx.Response(200, content='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+page_url+'</loc></url></urlset>'))

    # 2번의 타임아웃 에러 후 성공
    route = respx.get(page_url)
    route.side_effect = [httpx.TimeoutException("Timeout"), httpx.TimeoutException("Timeout"), httpx.Response(200, html="<html><body>Content</body></html>")]

    # 재시도 시간을 줄이기 위해 monkeypatch 활용 가능하지만 여기서는 timeout/retry를 작게 설정
    connector = SitemapConnector(url=url, max_retries=3, timeout=1.0)

    docs = []
    async for doc in connector.fetch_documents():
        docs.append(doc)

    assert len(docs) == 1
    assert route.call_count == 3 # 2번 재시도 + 1번 성공

@pytest.mark.asyncio
async def test_service_resilience_on_partial_failure():
    """일부 문서 처리 실패 시에도 전체 공정이 중단되지 않고 성공한 건은 저장되는지 확인"""
    # Given
    mock_vector_store = AsyncMock()
    mock_metadata_store = AsyncMock()
    mock_metadata_store.save.return_value = True

    # 1개는 정상, 1개는 에러를 뿜는 커넥터 모킹
    mock_connector = AsyncMock()
    async def mock_fetch():
        yield StandardDocument(content="Good Content", source_url="https://ok.com", metadata={"title": "OK"})
        # Chunker에서 에러를 유발하기 위해 content를 None으로 주거나 등 (여기서는 서비스 로직의 try-except 검증)
        yield StandardDocument(content=None, source_url="https://fail.com")

    mock_connector.fetch_documents = mock_fetch

    service = IngestionService(vector_store=mock_vector_store, metadata_store=mock_metadata_store)

    # When
    result = await service.ingest_from_connector(mock_connector, "test")

    # Then
    assert result.total_items == 2
    assert len(result.errors) > 0 # 에러가 기록됨
    assert result.metadata_saved >= 1 # 성공한 건은 저장됨
    mock_metadata_store.save.assert_called()
