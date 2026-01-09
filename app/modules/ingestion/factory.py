"""
Ingestion Connector Factory

설정에 따라 적절한 데이터 수집 커넥터를 생성합니다.
"""
from typing import Any

from app.modules.ingestion.connectors.sitemap import SitemapConnector
from app.modules.ingestion.interfaces import IIngestionConnector


class IngestionConnectorFactory:
    @staticmethod
    def create(config: dict[str, Any]) -> IIngestionConnector:
        connector_type = config.get("type")

        if connector_type == "web_sitemap":
            url = config.get("url")
            if not url:
                raise ValueError("URL is required for web_sitemap connector")
            # config에서 type과 url을 제외한 나머지 인자만 전달
            other_config = {k: v for k, v in config.items() if k not in ["type", "url"]}
            return SitemapConnector(url=url, **other_config)

        # 향후 LocalFolderConnector 등 추가 지점

        raise ValueError(f"Unsupported connector type: {connector_type}")
