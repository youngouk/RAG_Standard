"""
MongoDB Retriever 단위 테스트

현재 커버리지: 9.8%
목표 커버리지: 70-80%

테스트 범위:
- 초기화 및 연결 테스트
- 하이브리드 검색 (Client-side RRF)
- Vector Search 단독
- Full-Text Search 단독
- 에러 핸들링 (타임아웃, 빈 결과, 잘못된 벡터 차원)
- Fallback 메커니즘
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import PyMongoError


class TestMongoDBRetrieverInitialization:
    """MongoDB Retriever 초기화 및 연결 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query.return_value = [0.1] * 3072  # 3072d Gemini embedding
        return embedder

    @pytest.fixture
    def mock_mongodb_client(self) -> MagicMock:
        """Mock MongoDB Client"""
        client = MagicMock()
        client.ping.return_value = True

        # Mock collection
        mock_collection = MagicMock()
        mock_collection.count_documents.return_value = 100
        client.get_collection.return_value = mock_collection

        return client

    def test_initialization_success(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        MongoDB Retriever 초기화 성공 테스트

        Given: 유효한 embedder와 mongodb_client
        When: MongoDBRetriever 생성
        Then: 인스턴스 생성 성공, 기본값 설정 확인
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
            collection_name="test_docs",
            dense_weight=0.6,
            sparse_weight=0.4,
        )

        # 검증
        assert retriever.embedder == mock_embedder
        assert retriever.mongodb_client == mock_mongodb_client
        assert retriever.collection_name == "test_docs"
        assert retriever.dense_weight == 0.6
        assert retriever.sparse_weight == 0.4
        assert retriever.collection is None  # 초기화 전

    @pytest.mark.asyncio
    async def test_initialize_success(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        initialize() 성공 테스트

        Given: 정상 MongoDB 연결
        When: initialize() 호출
        Then: collection 설정, 문서 수 확인 성공
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # asyncio.to_thread Mock 처리
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = 100  # count_documents 결과

            await retriever.initialize()

            # 검증
            assert retriever.collection is not None
            mock_mongodb_client.ping.assert_called_once()
            mock_mongodb_client.get_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        initialize() 연결 실패 테스트

        Given: MongoDB 연결 실패 (ping() = False)
        When: initialize() 호출
        Then: RuntimeError 발생
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        # 연결 실패 시뮬레이션
        mock_mongodb_client.ping.return_value = False

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # 검증: RuntimeError 발생
        with pytest.raises(RuntimeError, match="MongoDB 연결이 활성화되지 않았습니다"):
            await retriever.initialize()

    @pytest.mark.asyncio
    async def test_initialize_collection_none(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        initialize() collection 가져오기 실패 테스트

        Given: get_collection() 반환 None
        When: initialize() 호출
        Then: RuntimeError 발생
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        # Collection 가져오기 실패
        mock_mongodb_client.get_collection.return_value = None

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # 검증
        with pytest.raises(RuntimeError, match="MongoDB 컬렉션을 가져올 수 없습니다"):
            await retriever.initialize()

    @pytest.mark.asyncio
    async def test_initialize_pymongo_error(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        initialize() PyMongoError 발생 테스트

        Given: MongoDB 연결 중 PyMongoError 발생
        When: initialize() 호출
        Then: PyMongoError 전파
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        # PyMongoError 시뮬레이션
        mock_mongodb_client.get_collection.side_effect = PyMongoError("Connection timeout")

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # 검증
        with pytest.raises(PyMongoError, match="Connection timeout"):
            await retriever.initialize()


class TestMongoDBRetrieverHealthCheck:
    """MongoDB health check 테스트"""

    @pytest.fixture
    def initialized_retriever(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> Any:
        """초기화된 MongoDB Retriever"""
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # collection 직접 설정 (initialize 우회)
        mock_collection = MagicMock()
        mock_collection.count_documents.return_value = 100
        retriever.collection = mock_collection

        return retriever

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query.return_value = [0.1] * 3072
        return embedder

    @pytest.fixture
    def mock_mongodb_client(self) -> MagicMock:
        """Mock MongoDB Client"""
        client = MagicMock()
        client.ping.return_value = True
        return client

    @pytest.mark.asyncio
    async def test_health_check_success(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        health_check() 성공 테스트

        Given: 정상 MongoDB 연결
        When: health_check() 호출
        Then: True 반환
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = 1  # count_documents 결과

            result = await initialized_retriever.health_check()

            # 검증
            assert result is True
            initialized_retriever.mongodb_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_collection_not_initialized(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        health_check() collection 미초기화 테스트

        Given: collection이 None
        When: health_check() 호출
        Then: False 반환
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # collection 초기화 안 함
        result = await retriever.health_check()

        # 검증
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_ping_failure(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        health_check() ping 실패 테스트

        Given: MongoDB ping() 실패
        When: health_check() 호출
        Then: False 반환
        """
        # ping 실패 시뮬레이션
        initialized_retriever.mongodb_client.ping.return_value = False

        result = await initialized_retriever.health_check()

        # 검증
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_pymongo_error(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        health_check() PyMongoError 발생 테스트

        Given: MongoDB 연결 중 PyMongoError
        When: health_check() 호출
        Then: False 반환 (에러 안전 처리)
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = PyMongoError("Connection lost")

            result = await initialized_retriever.health_check()

            # 검증
            assert result is False


class TestMongoDBRetrieverSearch:
    """MongoDB 검색 테스트 (하이브리드, Vector, Full-Text)"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query.return_value = [0.1] * 3072
        return embedder

    @pytest.fixture
    def mock_mongodb_client(self) -> MagicMock:
        """Mock MongoDB Client"""
        client = MagicMock()
        client.ping.return_value = True
        return client

    @pytest.fixture
    def initialized_retriever(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> Any:
        """초기화된 MongoDB Retriever"""
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # collection 설정
        mock_collection = MagicMock()
        retriever.collection = mock_collection

        return retriever

    @pytest.mark.asyncio
    async def test_search_hybrid_success(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        하이브리드 검색 성공 테스트 (Client-side RRF)

        Given: 쿼리와 top_k
        When: search() 호출
        Then: Vector + Full-Text 결과 통합 (RRF)
        """
        # Mock asyncio.gather 결과
        vector_results = [
            {
                "_id": "doc1",
                "content": "Vector 문서 1",
                "metadata": {},
                "score": 0.95,
            },
            {
                "_id": "doc2",
                "content": "Vector 문서 2",
                "metadata": {},
                "score": 0.85,
            },
        ]

        fulltext_results = [
            {
                "_id": "doc2",
                "content": "Full-text 문서 2",
                "metadata": {},
                "score": 0.9,
            },
            {
                "_id": "doc3",
                "content": "Full-text 문서 3",
                "metadata": {},
                "score": 0.8,
            },
        ]

        with patch("asyncio.to_thread") as mock_to_thread:
            # embedder.embed_query
            mock_to_thread.return_value = [0.1] * 3072

            # Mock _vector_search_only and _fulltext_search_only
            with patch.object(
                initialized_retriever,
                "_vector_search_only",
                return_value=vector_results,
            ):
                with patch.object(
                    initialized_retriever,
                    "_fulltext_search_only",
                    return_value=fulltext_results,
                ):
                    results = await initialized_retriever.search(
                        query="테스트 쿼리",
                        top_k=5,
                    )

                    # 검증
                    assert len(results) > 0
                    assert all(hasattr(result, "id") for result in results)
                    assert all(hasattr(result, "content") for result in results)
                    assert all(hasattr(result, "score") for result in results)

    @pytest.mark.asyncio
    async def test_search_collection_not_initialized(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> None:
        """
        search() collection 미초기화 테스트

        Given: collection이 None
        When: search() 호출
        Then: RuntimeError 발생
        """
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # collection 초기화 안 함
        with pytest.raises(RuntimeError, match="MongoDB 컬렉션이 초기화되지 않았습니다"):
            await retriever.search(query="테스트", top_k=10)

    @pytest.mark.asyncio
    async def test_search_invalid_embedding_type(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        search() 잘못된 임베딩 타입 테스트

        Given: embedder가 list가 아닌 타입 반환
        When: search() 호출
        Then: ValueError 발생
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            # 잘못된 타입 반환
            mock_to_thread.return_value = "invalid_type"

            with pytest.raises(ValueError, match="Embedding은 list 타입이어야 합니다"):
                await initialized_retriever.search(query="테스트", top_k=10)

    @pytest.mark.asyncio
    async def test_search_pymongo_error_fallback(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        search() PyMongoError 발생 시 Fallback 테스트

        Given: asyncio.gather에서 PyMongoError 발생
        When: search() 호출
        Then: _vector_search_fallback() 호출됨
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = [0.1] * 3072

            with patch("asyncio.gather") as mock_gather:
                # PyMongoError 발생
                mock_gather.side_effect = PyMongoError("Search failed")

                # Mock internal search methods to return non-coroutine objects (MagicMock)
                # Since asyncio.gather is mocked, it won't complain, and we avoid "coroutine never awaited" warning
                with patch.object(initialized_retriever, "_vector_search_only", new_callable=MagicMock), \
                     patch.object(initialized_retriever, "_fulltext_search_only", new_callable=MagicMock):

                    with patch.object(
                        initialized_retriever,
                        "_vector_search_fallback",
                        return_value=[],
                    ) as mock_fallback:
                        results = await initialized_retriever.search(
                            query="테스트",
                            top_k=10,
                        )

                        # 검증: Fallback 호출됨
                        mock_fallback.assert_called_once()
                        assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_results(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        search() 빈 결과 처리 테스트

        Given: Vector와 Full-Text 모두 빈 결과
        When: search() 호출
        Then: 빈 리스트 반환
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = [0.1] * 3072

            # Mock _vector_search_only and _fulltext_search_only
            with patch.object(
                initialized_retriever,
                "_vector_search_only",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch.object(
                    initialized_retriever,
                    "_fulltext_search_only",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    results = await initialized_retriever.search(
                        query="존재하지 않는 문서",
                        top_k=10,
                    )

                    # 검증
                    assert results == []


class TestMongoDBRetrieverClientSideRRF:
    """Client-side RRF 알고리즘 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        return MagicMock()

    @pytest.fixture
    def mock_mongodb_client(self) -> MagicMock:
        """Mock MongoDB Client"""
        return MagicMock()

    @pytest.fixture
    def retriever(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> Any:
        """Retriever 인스턴스"""
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        return MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
            dense_weight=0.6,
            sparse_weight=0.4,
        )

    def test_client_side_rrf_basic(
        self,
        retriever: Any,
    ) -> None:
        """
        Client-side RRF 기본 동작 테스트

        Given: Vector와 Full-Text 검색 결과
        When: _client_side_rank_fusion() 호출
        Then: RRF 점수로 정렬된 결과 반환
        """
        vector_results = [
            {"_id": "doc1", "content": "Vector 1", "metadata": {}, "score": 0.9},
            {"_id": "doc2", "content": "Vector 2", "metadata": {}, "score": 0.8},
        ]

        fulltext_results = [
            {"_id": "doc2", "content": "Full-text 2", "metadata": {}, "score": 0.95},
            {"_id": "doc3", "content": "Full-text 3", "metadata": {}, "score": 0.85},
        ]

        results = retriever._client_side_rank_fusion(
            vector_results=vector_results,
            fulltext_results=fulltext_results,
            top_k=3,
        )

        # 검증
        assert len(results) == 3
        # doc2가 양쪽에 모두 있으므로 최상위에 위치해야 함
        assert results[0].id == "doc2"

    def test_client_side_rrf_empty_vector(
        self,
        retriever: Any,
    ) -> None:
        """
        RRF Vector 결과 없음 테스트

        Given: Vector 결과 빈 리스트
        When: _client_side_rank_fusion() 호출
        Then: Full-text 결과만 반환
        """
        fulltext_results = [
            {"_id": "doc1", "content": "Full-text 1", "metadata": {}, "score": 0.9},
        ]

        results = retriever._client_side_rank_fusion(
            vector_results=[],
            fulltext_results=fulltext_results,
            top_k=5,
        )

        # 검증
        assert len(results) == 1
        assert results[0].id == "doc1"

    def test_client_side_rrf_empty_fulltext(
        self,
        retriever: Any,
    ) -> None:
        """
        RRF Full-text 결과 없음 테스트

        Given: Full-text 결과 빈 리스트
        When: _client_side_rank_fusion() 호출
        Then: Vector 결과만 반환
        """
        vector_results = [
            {"_id": "doc1", "content": "Vector 1", "metadata": {}, "score": 0.9},
        ]

        results = retriever._client_side_rank_fusion(
            vector_results=vector_results,
            fulltext_results=[],
            top_k=5,
        )

        # 검증
        assert len(results) == 1
        assert results[0].id == "doc1"

    def test_client_side_rrf_top_k_limit(
        self,
        retriever: Any,
    ) -> None:
        """
        RRF top_k 제한 테스트

        Given: 10개 결과, top_k=3
        When: _client_side_rank_fusion() 호출
        Then: 상위 3개만 반환
        """
        vector_results = [
            {"_id": f"doc{i}", "content": f"Doc {i}", "metadata": {}, "score": 0.9 - i * 0.1}
            for i in range(5)
        ]

        fulltext_results = [
            {"_id": f"doc{i}", "content": f"Doc {i}", "metadata": {}, "score": 0.8 - i * 0.1}
            for i in range(5, 10)
        ]

        results = retriever._client_side_rank_fusion(
            vector_results=vector_results,
            fulltext_results=fulltext_results,
            top_k=3,
        )

        # 검증
        assert len(results) == 3


class TestMongoDBRetrieverFallback:
    """Vector search fallback 테스트"""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Mock Embedder"""
        embedder = MagicMock()
        embedder.embed_query.return_value = [0.1] * 3072
        return embedder

    @pytest.fixture
    def mock_mongodb_client(self) -> MagicMock:
        """Mock MongoDB Client"""
        return MagicMock()

    @pytest.fixture
    def initialized_retriever(
        self,
        mock_embedder: MagicMock,
        mock_mongodb_client: MagicMock,
    ) -> Any:
        """초기화된 MongoDB Retriever"""
        from app.modules.core.retrieval.retrievers.mongodb_retriever import (
            MongoDBRetriever,
        )

        retriever = MongoDBRetriever(
            embedder=mock_embedder,
            mongodb_client=mock_mongodb_client,
        )

        # collection 설정
        mock_collection = MagicMock()
        retriever.collection = mock_collection

        return retriever

    @pytest.mark.asyncio
    async def test_vector_search_fallback_success(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        Vector search fallback 성공 테스트

        Given: 하이브리드 검색 실패
        When: _vector_search_fallback() 호출
        Then: Vector search 결과만 반환
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            # embedder.embed_query
            mock_to_thread.side_effect = [
                [0.1] * 3072,  # embed_query
                MagicMock(
                    __iter__=lambda self: iter(
                        [
                            {
                                "_id": "doc1",
                                "content": "Fallback 문서",
                                "metadata": {},
                                "score": 0.9,
                            }
                        ]
                    )
                ),  # aggregate cursor
                [
                    {
                        "_id": "doc1",
                        "content": "Fallback 문서",
                        "metadata": {},
                        "score": 0.9,
                    }
                ],  # list(cursor)
            ]

            results = await initialized_retriever._vector_search_fallback(
                query="테스트",
                top_k=10,
            )

            # 검증
            assert len(results) == 1
            assert results[0].id == "doc1"
            assert results[0].content == "Fallback 문서"

    @pytest.mark.asyncio
    async def test_vector_search_fallback_failure(
        self,
        initialized_retriever: Any,
    ) -> None:
        """
        Vector search fallback 실패 테스트

        Given: Fallback도 실패
        When: _vector_search_fallback() 호출
        Then: 빈 리스트 반환
        """
        with patch("asyncio.to_thread") as mock_to_thread:
            # Exception 발생
            mock_to_thread.side_effect = Exception("Fallback failed")

            results = await initialized_retriever._vector_search_fallback(
                query="테스트",
                top_k=10,
            )

            # 검증
            assert results == []
