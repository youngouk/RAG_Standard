"""
VectorStoreFactory 단위 테스트

설정 기반 벡터 스토어 생성 검증.
TDD 방식으로 작성 - 테스트 먼저, 구현 나중.

테스트 케이스:
1. 등록된 provider 목록 조회
2. 알 수 없는 provider에 ValueError 발생
3. weaviate provider가 목록에 존재 확인 (실제 연결 없이)
"""

from unittest.mock import MagicMock, patch

import pytest


class TestVectorStoreFactoryRegistry:
    """VectorStoreFactory 레지스트리 테스트"""

    def test_get_available_providers_returns_list(self):
        """get_available_providers()가 리스트를 반환하는지 확인"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        providers = VectorStoreFactory.get_available_providers()

        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_available_providers_contains_weaviate(self):
        """weaviate가 provider 목록에 포함되어 있는지 확인"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        providers = VectorStoreFactory.get_available_providers()

        assert "weaviate" in providers

    def test_register_provider_adds_new_provider(self):
        """register_provider()로 새 provider 등록이 가능한지 확인"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        # 새 provider 등록
        VectorStoreFactory.register_provider(
            name="test-provider",
            class_path="app.infrastructure.storage.vector.test_store.TestVectorStore"
        )

        providers = VectorStoreFactory.get_available_providers()
        assert "test-provider" in providers

        # 테스트 후 정리 (다른 테스트에 영향 방지)
        VectorStoreFactory._providers.pop("test-provider", None)


class TestVectorStoreFactoryCreate:
    """VectorStoreFactory.create() 메서드 테스트"""

    def test_create_unknown_provider_raises_value_error(self):
        """알 수 없는 provider로 생성 시 ValueError 발생"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        with pytest.raises(ValueError) as exc_info:
            VectorStoreFactory.create(
                provider="unknown-db",
                config={}
            )

        # 에러 메시지에 사용 가능한 provider 목록이 포함되어 있는지 확인
        error_message = str(exc_info.value)
        assert "unknown-db" in error_message
        assert "weaviate" in error_message or "지원하지 않는" in error_message

    def test_create_weaviate_provider_exists_in_registry(self):
        """weaviate provider가 레지스트리에 등록되어 있는지 확인"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        providers = VectorStoreFactory.get_available_providers()

        # weaviate가 기본 등록되어 있어야 함
        assert "weaviate" in providers

    @patch.dict("os.environ", {"WEAVIATE_URL": "http://localhost:8080"})
    def test_create_weaviate_returns_ivectorstore_instance(self):
        """weaviate provider로 IVectorStore 인스턴스 생성 확인 (Mock 사용)"""
        from app.core.interfaces.storage import IVectorStore
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        # Weaviate 클라이언트 연결을 Mock 처리
        with patch("weaviate.connect_to_custom") as mock_connect:
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            store = VectorStoreFactory.create(
                provider="weaviate",
                config={"url": "http://localhost:8080"}
            )

            # IVectorStore 인터페이스를 구현하는지 확인
            assert isinstance(store, IVectorStore)


class TestVectorStoreFactoryLazyImport:
    """VectorStoreFactory 지연 로딩 테스트"""

    def test_missing_library_raises_import_error_with_friendly_message(self):
        """라이브러리 미설치 시 친절한 ImportError 발생"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        # 가상의 provider 등록 (존재하지 않는 모듈 경로)
        VectorStoreFactory.register_provider(
            name="fake-db",
            class_path="app.infrastructure.storage.vector.fake_store.FakeVectorStore"
        )

        with pytest.raises(ImportError) as exc_info:
            VectorStoreFactory.create(
                provider="fake-db",
                config={}
            )

        error_message = str(exc_info.value)
        # 친절한 에러 메시지 확인
        assert "fake-db" in error_message or "설치" in error_message or "install" in error_message.lower()

        # 테스트 후 정리
        VectorStoreFactory._providers.pop("fake-db", None)


class TestVectorStoreFactoryProviderInfo:
    """VectorStoreFactory provider 정보 조회 테스트"""

    def test_get_provider_info_returns_class_path(self):
        """provider 정보에 class_path가 포함되어 있는지 확인"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        # weaviate provider의 class_path 확인
        provider_info = VectorStoreFactory.get_provider_info("weaviate")

        assert provider_info is not None
        assert "class_path" in provider_info
        assert "WeaviateVectorStore" in provider_info["class_path"]

    def test_get_provider_info_unknown_returns_none(self):
        """존재하지 않는 provider 조회 시 None 반환"""
        from app.infrastructure.storage.vector.factory import VectorStoreFactory

        provider_info = VectorStoreFactory.get_provider_info("non-existent-db")

        assert provider_info is None
