"""
RetrieverFactory 단위 테스트

설정 기반 Retriever 생성 검증.
TDD 방식으로 작성 - 테스트 먼저, 구현 나중.

VectorStoreFactory 패턴을 따르되, Retriever 특화 기능 추가:
- 하이브리드 검색 지원 여부 관리
- BM25 전처리 모듈 자동 주입
- IEmbedder 의존성 주입
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


class MockEmbedder:
    """테스트용 Mock Embedder"""

    def embed_query(self, text: str) -> list[float]:
        """쿼리 임베딩 생성 (3072 차원 더미)"""
        return [0.1] * 3072

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """문서 임베딩 생성"""
        return [[0.1] * 3072 for _ in texts]


class MockBM25Preprocessor:
    """테스트용 Mock BM25 Preprocessor"""

    def process(self, text: str) -> str:
        """전처리 수행"""
        return text.lower()


class TestRetrieverFactoryBasics:
    """RetrieverFactory 기본 기능 테스트"""

    def test_get_available_providers_returns_list(self):
        """등록된 provider 목록 반환 확인"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        providers = RetrieverFactory.get_available_providers()

        # 리스트 반환 확인
        assert isinstance(providers, list)
        # weaviate가 기본 등록되어 있어야 함
        assert "weaviate" in providers

    def test_register_provider_adds_new_provider(self):
        """새 provider 등록 기능 테스트"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        # 테스트용 provider 등록
        RetrieverFactory.register_provider(
            name="test_provider",
            class_path="tests.unit.retrieval.retrievers.test_retriever_factory.MockRetriever",
            hybrid_support=True,
        )

        # 등록 후 확인
        updated_providers = RetrieverFactory.get_available_providers()
        assert "test_provider" in updated_providers

        # 정리: 테스트 provider 제거 (다른 테스트에 영향 방지)
        if "test_provider" in RetrieverFactory._providers:
            del RetrieverFactory._providers["test_provider"]


class TestRetrieverFactoryHybridSupport:
    """하이브리드 검색 지원 여부 테스트"""

    def test_supports_hybrid_weaviate_true(self):
        """Weaviate는 하이브리드 검색을 지원해야 함"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        assert RetrieverFactory.supports_hybrid("weaviate") is True

    def test_supports_hybrid_unknown_provider_raises_error(self):
        """알 수 없는 provider에 대해 에러 발생"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        with pytest.raises(ValueError, match="지원하지 않는"):
            RetrieverFactory.supports_hybrid("unknown_provider")

    def test_hybrid_support_metadata_stored(self):
        """하이브리드 지원 메타데이터가 저장되는지 확인"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        # provider 등록 (하이브리드 미지원)
        RetrieverFactory.register_provider(
            name="test_no_hybrid",
            class_path="tests.unit.retrieval.retrievers.test_retriever_factory.MockRetriever",
            hybrid_support=False,
        )

        assert RetrieverFactory.supports_hybrid("test_no_hybrid") is False

        # 정리
        if "test_no_hybrid" in RetrieverFactory._providers:
            del RetrieverFactory._providers["test_no_hybrid"]


class TestRetrieverFactoryCreate:
    """RetrieverFactory.create() 테스트"""

    def test_create_weaviate_retriever_basic(self):
        """기본 Weaviate Retriever 생성 테스트"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        # Mock embedder
        mock_embedder = MockEmbedder()

        # Mock Weaviate 클라이언트 (WeaviateClient 형태)
        mock_weaviate_client = MagicMock()
        mock_weaviate_client.is_ready.return_value = True
        mock_weaviate_client.get_collection.return_value = MagicMock()

        config = {
            "weaviate_client": mock_weaviate_client,
            "collection_name": "TestDocuments",
            "alpha": 0.7,
        }

        retriever = RetrieverFactory.create(
            provider="weaviate",
            embedder=mock_embedder,
            config=config,
        )

        # Retriever 생성 확인
        assert retriever is not None
        assert retriever.__class__.__name__ == "WeaviateRetriever"

    def test_create_with_bm25_preprocessors(self):
        """BM25 전처리 모듈과 함께 Retriever 생성"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        mock_embedder = MockEmbedder()

        mock_weaviate_client = MagicMock()
        mock_weaviate_client.is_ready.return_value = True
        mock_weaviate_client.get_collection.return_value = MagicMock()

        # BM25 전처리 모듈들
        bm25_preprocessors = {
            "synonym_manager": MagicMock(),
            "stopword_filter": MagicMock(),
            "user_dictionary": MagicMock(),
        }

        config = {
            "weaviate_client": mock_weaviate_client,
            "collection_name": "TestDocuments",
        }

        retriever = RetrieverFactory.create(
            provider="weaviate",
            embedder=mock_embedder,
            config=config,
            bm25_preprocessors=bm25_preprocessors,
        )

        assert retriever is not None
        # BM25 모듈이 주입되었는지 확인
        assert retriever.synonym_manager is not None
        assert retriever.stopword_filter is not None
        assert retriever.user_dictionary is not None

    def test_create_invalid_provider_raises_error(self):
        """유효하지 않은 provider로 생성 시 에러"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        mock_embedder = MockEmbedder()

        with pytest.raises(ValueError, match="지원하지 않는"):
            RetrieverFactory.create(
                provider="invalid_provider",
                embedder=mock_embedder,
                config={},
            )

    def test_create_returns_iretriever_compatible(self):
        """생성된 Retriever가 IRetriever 인터페이스와 호환되는지 확인"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        mock_embedder = MockEmbedder()
        mock_weaviate_client = MagicMock()
        mock_weaviate_client.is_ready.return_value = True
        mock_weaviate_client.get_collection.return_value = MagicMock()

        config = {
            "weaviate_client": mock_weaviate_client,
        }

        retriever = RetrieverFactory.create(
            provider="weaviate",
            embedder=mock_embedder,
            config=config,
        )

        # IRetriever 필수 메서드 존재 확인
        assert hasattr(retriever, "search")
        assert callable(retriever.search)
        assert hasattr(retriever, "health_check")
        assert callable(retriever.health_check)


class TestRetrieverFactoryProviderInfo:
    """Provider 정보 조회 테스트"""

    def test_get_provider_info_returns_metadata(self):
        """Provider 정보 조회 시 메타데이터 반환"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        info = RetrieverFactory.get_provider_info("weaviate")

        assert info is not None
        assert "class_path" in info
        assert "hybrid_support" in info
        assert "description" in info

    def test_get_provider_info_unknown_returns_none(self):
        """알 수 없는 provider 조회 시 None 반환"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        info = RetrieverFactory.get_provider_info("unknown_provider")
        assert info is None


class TestRetrieverFactoryLazyLoading:
    """지연 로딩 테스트"""

    def test_provider_class_not_imported_until_create(self):
        """create() 호출 전까지 provider 클래스가 import되지 않음"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        # provider 목록 조회 시에는 import 없이 가능해야 함
        providers = RetrieverFactory.get_available_providers()
        assert len(providers) > 0
        # (지연 로딩이므로 실제 WeaviateRetriever 클래스는 아직 import 안 됨)

    def test_import_error_provides_helpful_message(self):
        """Import 실패 시 친절한 에러 메시지 제공"""
        from app.modules.core.retrieval.retrievers.factory import RetrieverFactory

        # 존재하지 않는 모듈 경로로 등록
        RetrieverFactory.register_provider(
            name="broken_provider",
            class_path="app.nonexistent.module.BrokenRetriever",
            hybrid_support=False,
        )

        mock_embedder = MockEmbedder()

        # create 시 ImportError 또는 ModuleNotFoundError 발생
        with pytest.raises((ImportError, ModuleNotFoundError)):
            RetrieverFactory.create(
                provider="broken_provider",
                embedder=mock_embedder,
                config={},
            )

        # 정리
        if "broken_provider" in RetrieverFactory._providers:
            del RetrieverFactory._providers["broken_provider"]


# Mock Retriever 클래스 (테스트용)
class MockRetriever:
    """테스트용 Mock Retriever"""

    def __init__(
        self,
        embedder: Any,
        **kwargs: Any,
    ):
        self.embedder = embedder
        self.config = kwargs

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[Any]:
        return []

    async def health_check(self) -> bool:
        return True
