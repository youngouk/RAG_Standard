"""
Sitemap Connector Unit Test

실제 웹 호출 없이 모킹된 응답을 통해 사이트맵 분석 및 본문 추출 로직을 검증합니다.
"""
import httpx
import pytest
import respx

from app.modules.ingestion.connectors.sitemap import SitemapConnector
from app.modules.ingestion.interfaces import StandardDocument


@pytest.mark.asyncio
@respx.mock
async def test_sitemap_connector_fetches_and_parses():
    """사이트맵을 읽고 하위 페이지들의 내용을 추출하는지 확인"""
    # Given
    sitemap_url = "https://example.com/sitemap.xml"
    page_url = "https://example.com/page1"

    # 1. Sitemap XML Mocking
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <url><loc>{page_url}</loc></url>
    </urlset>
    """
    respx.get(sitemap_url).mock(return_value=httpx.Response(200, content=sitemap_xml))

    # 2. Page HTML Mocking
    page_html = "<html><body><article><h1>제목</h1><p>본문 내용입니다.</p></article></body></html>"
    respx.get(page_url).mock(return_value=httpx.Response(200, html=page_html))

    connector = SitemapConnector(url=sitemap_url)

    # When
    docs = []
    async for doc in connector.fetch_documents():
        docs.append(doc)

    # Then
    assert len(docs) == 1
    assert isinstance(docs[0], StandardDocument)
    assert "본문 내용입니다" in docs[0].content
    assert docs[0].source_url == page_url
