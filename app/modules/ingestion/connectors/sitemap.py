"""
Sitemap Connector Implementation

사이트맵 XML을 분석하고 각 페이지의 본문을 추출하는 실질적인 구현체.

변경 이력:
- 2026-01-08: QA-001 대응 - encoding 모듈 import 추가 (향후 파일 처리 확장 대비)
"""
import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.modules.ingestion.interfaces import IIngestionConnector, StandardDocument

logger = logging.getLogger(__name__)

class SitemapConnector(IIngestionConnector):
    def __init__(self, url: str, **kwargs: Any) -> None:
        self.url = url
        self.timeout = kwargs.get("timeout", 30.0)
        self.max_parallel = kwargs.get("max_parallel", 5) # 동시 요청 제한
        self.max_retries = kwargs.get("max_retries", 3)
        self._semaphore = asyncio.Semaphore(self.max_parallel)

    async def fetch_documents(self) -> AsyncGenerator[StandardDocument, None]:
        """사이트맵에서 URL 목록을 가져와 각 페이지의 내용을 병렬로 추출"""
        urls = await self._parse_sitemap(self.url)
        if not urls:
            logger.warning(f"No URLs found in sitemap: {self.url}")
            return

        # 병렬 태스크 생성
        tasks = [self._safe_fetch_and_parse(url) for url in urls]

        # 결과를 스트리밍하기 위해 as_completed 사용
        for task in asyncio.as_completed(tasks):
            try:
                doc = await task
                if doc:
                    yield doc
            except Exception as e:
                logger.error(f"Critical error during document fetch task: {e}")

    async def _safe_fetch_and_parse(self, url: str) -> StandardDocument | None:
        """세마포어와 재시도 로직을 적용한 안전한 페이지 수집"""
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        return await self._fetch_and_parse_page(client, url)
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to fetch {url} after {self.max_retries} retries: {e}")
                        return None
                    wait_time = (attempt + 1) * 2 # 단순 지수 백오프
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} for {url} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Non-retryable error for {url}: {e}")
                    return None
        return None

    async def _parse_sitemap(self, sitemap_url: str) -> list[str]:
        """사이트맵 XML에서 <loc> 태그의 URL 목록 추출"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(sitemap_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")
            urls = [loc.text.strip() for loc in soup.find_all("loc")]
            logger.info(f"Found {len(urls)} URLs in sitemap {sitemap_url}")
            return urls

    async def _fetch_and_parse_page(self, client: httpx.AsyncClient, url: str) -> StandardDocument:
        """단일 HTML 페이지에서 본문 텍스트 추출"""
        response = await client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 1. 불필요한 태그 제거 (스크립트, 스타일, 네비게이션 등)
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # 2. 본문으로 추정되는 태그 찾기 (article -> main -> body 순)
        body = soup.find("article") or soup.find("main") or soup.find("body")

        # 3. 텍스트 추출 및 정제
        text = body.get_text(separator="\n").strip() if body else ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        title = soup.title.string if soup.title else url

        return StandardDocument(
            content=cleaned_text,
            source_url=url,
            metadata={
                "title": title,
                "type": "web_page"
            }
        )
