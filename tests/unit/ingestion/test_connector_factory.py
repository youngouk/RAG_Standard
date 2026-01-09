"""
Ingestion Connector Factory Test

다양한 데이터 소스 커넥터가 인터페이스를 준수하고,
팩토리를 통해 올바르게 생성되는지 검증합니다.
"""

import pytest

from app.modules.ingestion.factory import IngestionConnectorFactory
from app.modules.ingestion.interfaces import IIngestionConnector


@pytest.mark.asyncio
async def test_connector_factory_creates_sitemap_connector():
    """팩토리가 sitemap 타입의 커넥터를 올바르게 생성하는지 확인"""
    # Given
    config = {"type": "web_sitemap", "url": "https://example.com/sitemap.xml"}

    # When
    connector = IngestionConnectorFactory.create(config)

    # Then
    assert connector is not None
    assert isinstance(connector, IIngestionConnector)

@pytest.mark.asyncio
async def test_invalid_connector_type_raises_error():
    """지원하지 않는 커넥터 타입 요청 시 에러 발생 확인"""
    with pytest.raises(ValueError, match="Unsupported connector type"):
        IngestionConnectorFactory.create({"type": "invalid_type"})
