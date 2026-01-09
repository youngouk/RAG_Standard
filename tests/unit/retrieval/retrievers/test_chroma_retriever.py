"""
Chroma Retriever 단위 테스트

ChromaRetriever는 Dense 전용 검색만 지원합니다.
하이브리드 검색(BM25)은 지원하지 않습니다.

테스트 전략:
1. 연결 및 초기화 테스트
2. Dense 검색 테스트
3. 빈 결과 및 에러 핸들링
4. Health Check
5. IRetriever Protocol 준수 확인
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

# chromadb 선택적 의존성 - 미설치 환경에서도 테스트 로드 가능
chromadb = pytest.importorskip("chromadb")


class TestChromaRetrieverInitialization:
    """ChromaRetriever 초기화 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder - 3072 차원 벡터 반환"""
        embedder = MagicMock()
        embedder.embed_query = MagicMock(return_value=[0.1] * 3072)
        return embedder

    @pytest.fixture
    def mock_chroma_store(self) -> MagicMock:
        """Mock ChromaVectorStore"""
        store = MagicMock()
        # search 메서드는 비동기로 구현
        store.search = MagicMock()
        return store

    def test_init_with_defaults(
        self, mock_embedder: MagicMock, mock_chroma_store: MagicMock
    ) -> None:
        """
        기본 파라미터로 초기화 테스트

        Given: embedder와 store만 제공
        When: ChromaRetriever 생성
        Then: 기본값으로 초기화됨 (collection_name="documents", top_k=10)
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_chroma_store,
        )

        # 검증: 기본값 설정
        assert retriever.embedder == mock_embedder
        assert retriever.store == mock_chroma_store
        assert retriever.collection_name == "documents"
        assert retriever.top_k == 10

    def test_init_with_custom_params(
        self, mock_embedder: MagicMock, mock_chroma_store: MagicMock
    ) -> None:
        """
        커스텀 파라미터로 초기화 테스트

        Given: 커스텀 collection_name과 top_k 제공
        When: ChromaRetriever 생성
        Then: 커스텀 값으로 초기화됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_chroma_store,
            collection_name="my_documents",
            top_k=20,
        )

        # 검증: 커스텀 값 설정
        assert retriever.collection_name == "my_documents"
        assert retriever.top_k == 20


class TestChromaRetrieverSearch:
    """ChromaRetriever 검색 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder - 3072 차원 벡터 반환"""
        embedder = MagicMock()
        embedder.embed_query = MagicMock(return_value=[0.1] * 3072)
        return embedder

    @pytest.fixture
    def mock_chroma_store_with_results(self) -> MagicMock:
        """검색 결과를 반환하는 Mock ChromaVectorStore"""
        store = MagicMock()

        # 비동기 search 결과 Mock
        async def mock_search(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "_id": "doc-1",
                    "_distance": 0.15,
                    "content": "테스트 문서 1",
                    "source": "test1.md",
                    "file_type": "MARKDOWN",
                },
                {
                    "_id": "doc-2",
                    "_distance": 0.25,
                    "content": "테스트 문서 2",
                    "source": "test2.md",
                    "file_type": "MARKDOWN",
                },
            ]

        store.search = mock_search
        return store

    @pytest.mark.asyncio
    async def test_search_returns_search_results(
        self, mock_embedder: MagicMock, mock_chroma_store_with_results: MagicMock
    ) -> None:
        """
        검색 시 SearchResult 리스트 반환 테스트

        Given: 문서가 있는 ChromaVectorStore
        When: search() 호출
        Then: SearchResult 리스트 반환 (id, content, score, metadata 포함)
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_chroma_store_with_results,
            collection_name="documents",
        )

        # 검색 수행
        results = await retriever.search(query="테스트 쿼리", top_k=10)

        # 검증: SearchResult 형식
        assert len(results) == 2

        # 첫 번째 결과 검증
        assert results[0].id == "doc-1"
        assert results[0].content == "테스트 문서 1"
        # distance를 score로 변환 (1 - distance)
        assert results[0].score == pytest.approx(0.85, abs=0.01)
        assert results[0].metadata["source"] == "test1.md"
        assert results[0].metadata["file_type"] == "MARKDOWN"

        # 두 번째 결과 검증
        assert results[1].id == "doc-2"
        assert results[1].content == "테스트 문서 2"
        assert results[1].score == pytest.approx(0.75, abs=0.01)

    @pytest.mark.asyncio
    async def test_search_uses_embedder(
        self, mock_embedder: MagicMock, mock_chroma_store_with_results: MagicMock
    ) -> None:
        """
        검색 시 embedder를 사용하여 쿼리 벡터화 테스트

        Given: embedder와 store가 설정된 retriever
        When: search() 호출
        Then: embedder.embed_query()가 호출됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_chroma_store_with_results,
            collection_name="documents",
        )

        # 검색 수행
        await retriever.search(query="임베딩 테스트", top_k=5)

        # 검증: embed_query 호출됨
        mock_embedder.embed_query.assert_called_once_with("임베딩 테스트")

    @pytest.mark.asyncio
    async def test_search_empty_results(
        self, mock_embedder: MagicMock
    ) -> None:
        """
        빈 결과 처리 테스트

        Given: 검색 결과가 없는 store
        When: search() 호출
        Then: 빈 리스트 반환, 에러 없음
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 빈 결과 반환하는 store
        mock_store = MagicMock()

        async def mock_search_empty(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return []

        mock_store.search = mock_search_empty

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # 검색 수행
        results = await retriever.search(query="없는 문서", top_k=10)

        # 검증: 빈 리스트 반환
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, mock_embedder: MagicMock
    ) -> None:
        """
        필터를 사용한 검색 테스트

        Given: 필터 조건 제공
        When: search() 호출
        Then: store.search()에 필터 전달됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 필터 검증용 store
        mock_store = MagicMock()
        captured_filters: dict[str, Any] = {}

        async def mock_search_capture_filters(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            if filters:
                captured_filters.update(filters)
            return []

        mock_store.search = mock_search_capture_filters

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # 필터와 함께 검색
        filters = {"file_type": "PDF"}
        await retriever.search(query="필터 테스트", top_k=10, filters=filters)

        # 검증: 필터가 전달됨
        assert captured_filters == {"file_type": "PDF"}

    @pytest.mark.asyncio
    async def test_search_respects_top_k(
        self, mock_embedder: MagicMock
    ) -> None:
        """
        top_k 파라미터 존중 테스트

        Given: top_k 파라미터 제공
        When: search() 호출
        Then: store.search()에 top_k 전달됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # top_k 검증용 store
        mock_store = MagicMock()
        captured_top_k: list[int] = []

        async def mock_search_capture_top_k(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            captured_top_k.append(top_k)
            return []

        mock_store.search = mock_search_capture_top_k

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # 다양한 top_k로 검색
        await retriever.search(query="테스트", top_k=5)
        await retriever.search(query="테스트", top_k=20)

        # 검증: top_k가 올바르게 전달됨
        assert captured_top_k == [5, 20]


class TestChromaRetrieverHealthCheck:
    """ChromaRetriever Health Check 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_embedder: MagicMock) -> None:
        """
        Health Check 성공 테스트

        Given: 정상 동작하는 store
        When: health_check() 호출
        Then: True 반환
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 정상 동작하는 store
        mock_store = MagicMock()

        async def mock_search_ok(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return []

        mock_store.search = mock_search_ok

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # Health Check
        is_healthy = await retriever.health_check()

        # 검증: True 반환
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_embedder: MagicMock) -> None:
        """
        Health Check 실패 테스트

        Given: store 검색이 실패하는 경우
        When: health_check() 호출
        Then: False 반환
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 에러 발생하는 store
        mock_store = MagicMock()

        async def mock_search_error(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            raise RuntimeError("Connection failed")

        mock_store.search = mock_search_error

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # Health Check
        is_healthy = await retriever.health_check()

        # 검증: False 반환
        assert is_healthy is False


class TestChromaRetrieverErrorHandling:
    """ChromaRetriever 에러 핸들링 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query = MagicMock(return_value=[0.1] * 3072)
        return embedder

    @pytest.mark.asyncio
    async def test_embedding_error_propagation(self, mock_embedder: MagicMock) -> None:
        """
        Embedding 에러 전파 테스트

        Given: embedder가 에러 발생
        When: search() 호출
        Then: 에러 전파됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 에러 발생하는 embedder
        mock_embedder.embed_query = MagicMock(
            side_effect=ValueError("Embedding failed")
        )

        mock_store = MagicMock()

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # 검색 시도 - 에러 전파되어야 함
        with pytest.raises(ValueError) as exc_info:
            await retriever.search(query="테스트", top_k=10)

        assert "Embedding failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_error_propagation(self, mock_embedder: MagicMock) -> None:
        """
        Store 검색 에러 전파 테스트

        Given: store.search()가 에러 발생
        When: search() 호출
        Then: 에러 전파됨
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 에러 발생하는 store
        mock_store = MagicMock()

        async def mock_search_error(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            raise RuntimeError("Search failed")

        mock_store.search = mock_search_error

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
            collection_name="documents",
        )

        # 검색 시도 - 에러 전파되어야 함
        with pytest.raises(RuntimeError) as exc_info:
            await retriever.search(query="테스트", top_k=10)

        assert "Search failed" in str(exc_info.value)


class TestChromaRetrieverProtocolCompliance:
    """IRetriever Protocol 준수 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query = MagicMock(return_value=[0.1] * 3072)
        return embedder

    @pytest.fixture
    def mock_chroma_store(self) -> MagicMock:
        """Mock ChromaVectorStore"""
        store = MagicMock()

        async def mock_search(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return []

        store.search = mock_search
        return store

    def test_implements_iretriever_protocol(
        self, mock_embedder: MagicMock, mock_chroma_store: MagicMock
    ) -> None:
        """
        IRetriever Protocol 구현 확인 테스트

        Given: ChromaRetriever 인스턴스
        When: Protocol 메서드 확인
        Then: search(), health_check() 메서드 존재
        """
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_chroma_store,
        )

        # 검증: 필수 메서드 존재
        assert hasattr(retriever, "search")
        assert callable(retriever.search)
        assert hasattr(retriever, "health_check")
        assert callable(retriever.health_check)

    @pytest.mark.asyncio
    async def test_search_returns_search_result_type(
        self, mock_embedder: MagicMock
    ) -> None:
        """
        search() 반환 타입이 SearchResult인지 확인

        Given: 검색 결과가 있는 retriever
        When: search() 호출
        Then: SearchResult 인스턴스 리스트 반환
        """
        from app.modules.core.retrieval.interfaces import SearchResult
        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # 결과 반환하는 store
        mock_store = MagicMock()

        async def mock_search(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "_id": "doc-1",
                    "_distance": 0.1,
                    "content": "테스트",
                }
            ]

        mock_store.search = mock_search

        retriever = ChromaRetriever(
            embedder=mock_embedder,
            store=mock_store,
        )

        results = await retriever.search(query="테스트", top_k=10)

        # 검증: SearchResult 타입
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)


class TestChromaRetrieverNoHybridSupport:
    """ChromaRetriever 하이브리드 미지원 확인 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        return MagicMock()

    @pytest.fixture
    def mock_chroma_store(self) -> MagicMock:
        """Mock ChromaVectorStore"""
        store = MagicMock()

        async def mock_search(
            collection: str,
            query_vector: list[float],
            top_k: int,
            filters: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            return []

        store.search = mock_search
        return store

    def test_no_bm25_parameters(
        self, mock_embedder: MagicMock, mock_chroma_store: MagicMock
    ) -> None:
        """
        BM25 관련 파라미터가 없는지 확인

        Given: ChromaRetriever 생성자
        When: __init__ 시그니처 확인
        Then: bm25_preprocessors, synonym_manager, stopword_filter 등 없음
        """
        import inspect

        from app.modules.core.retrieval.retrievers.chroma_retriever import (
            ChromaRetriever,
        )

        # __init__ 시그니처 확인
        sig = inspect.signature(ChromaRetriever.__init__)
        param_names = list(sig.parameters.keys())

        # BM25 관련 파라미터가 없어야 함
        bm25_params = [
            "synonym_manager",
            "stopword_filter",
            "user_dictionary",
            "bm25_preprocessors",
            "alpha",  # 하이브리드 가중치
        ]

        for param in bm25_params:
            assert param not in param_names, f"{param}은 ChromaRetriever에 있으면 안 됨"
