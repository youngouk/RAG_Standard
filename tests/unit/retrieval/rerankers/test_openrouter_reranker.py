"""
OpenRouterReranker 단위 테스트

OpenRouter API 기반 LLM 리랭커 테스트.
TDD 기반으로 작성됨.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.core.retrieval.interfaces import SearchResult


class TestOpenRouterRerankerInitialization:
    """초기화 테스트"""

    def test_init_with_valid_api_key(self):
        """유효한 API 키로 초기화"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        assert reranker.api_key == "test-key"
        assert reranker.model == "google/gemini-2.5-flash-lite"

    def test_init_without_api_key_raises_error(self):
        """API 키 없이 초기화 시 에러"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        with pytest.raises(ValueError, match="API key"):
            OpenRouterReranker(api_key="")

    def test_init_with_custom_model(self):
        """커스텀 모델로 초기화"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(
            api_key="test-key", model="anthropic/claude-3-haiku"
        )
        assert reranker.model == "anthropic/claude-3-haiku"

    def test_init_with_custom_timeout(self):
        """커스텀 타임아웃으로 초기화"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key", timeout=30)
        assert reranker.timeout == 30

    def test_init_with_custom_max_documents(self):
        """커스텀 max_documents로 초기화"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key", max_documents=50)
        assert reranker.max_documents == 50

    @pytest.mark.asyncio
    async def test_initialize_method(self):
        """initialize 메서드 호출"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        # initialize는 에러 없이 완료되어야 함
        await reranker.initialize()

    @pytest.mark.asyncio
    async def test_close_method(self):
        """close 메서드로 리소스 정리"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        # close는 에러 없이 완료되어야 함
        await reranker.close()


class TestOpenRouterRerankerReranking:
    """리랭킹 기능 테스트"""

    @pytest.fixture
    def sample_results(self) -> list[SearchResult]:
        """테스트용 샘플 검색 결과"""
        return [
            SearchResult(id="1", content="문서 1 내용", score=0.8, metadata={}),
            SearchResult(id="2", content="문서 2 내용", score=0.6, metadata={}),
            SearchResult(id="3", content="문서 3 내용", score=0.4, metadata={}),
        ]

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self):
        """빈 결과 리랭킹 시 빈 리스트 반환"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        result = await reranker.rerank("쿼리", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_success(self, sample_results: list[SearchResult]):
        """정상 리랭킹 - API 응답 파싱 및 결과 재구성"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 1, "score": 0.95}, {"index": 0, "score": 0.85}, {"index": 2, "score": 0.70}]}'
                    }
                }
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        # HTTP 클라이언트 모킹
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # 결과 검증
            assert len(result) == 3
            assert result[0].score == 0.95
            assert result[0].id == "2"  # index 1 → id "2"
            assert result[1].score == 0.85
            assert result[1].id == "1"  # index 0 → id "1"
            assert result[2].score == 0.70
            assert result[2].id == "3"  # index 2 → id "3"

    @pytest.mark.asyncio
    async def test_rerank_with_top_n(self, sample_results: list[SearchResult]):
        """top_n 파라미터로 결과 수 제한"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 1, "score": 0.95}, {"index": 0, "score": 0.85}, {"index": 2, "score": 0.70}]}'
                    }
                }
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results, top_n=2)

            # top_n=2이므로 2개만 반환
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_truncates_to_max_documents(self):
        """max_documents 초과 시 잘림"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        # 5개 문서 생성
        many_results = [
            SearchResult(id=str(i), content=f"문서 {i}", score=0.5, metadata={})
            for i in range(5)
        ]

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 0, "score": 0.9}, {"index": 1, "score": 0.8}]}'
                    }
                }
            ]
        }

        # max_documents=2로 설정
        reranker = OpenRouterReranker(api_key="test-key", max_documents=2)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("쿼리", many_results)

            # max_documents=2이므로 2개만 처리됨
            assert len(result) <= 2


class TestOpenRouterRerankerErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def sample_results(self) -> list[SearchResult]:
        """테스트용 샘플 검색 결과"""
        return [
            SearchResult(id="1", content="문서 1 내용", score=0.8, metadata={}),
        ]

    @pytest.mark.asyncio
    async def test_timeout_returns_original(self, sample_results: list[SearchResult]):
        """타임아웃 시 원본 결과 반환 (Graceful Fallback)"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key", timeout=1)

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timeout")

            result = await reranker.rerank("쿼리", sample_results)

            # 타임아웃 시 원본 반환
            assert result == sample_results

    @pytest.mark.asyncio
    async def test_http_error_returns_original(self, sample_results: list[SearchResult]):
        """HTTP 에러 시 원본 결과 반환"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=mock_request, response=mock_response
            )

            result = await reranker.rerank("쿼리", sample_results)

            # HTTP 에러 시 원본 반환
            assert result == sample_results

    @pytest.mark.asyncio
    async def test_invalid_json_returns_original(
        self, sample_results: list[SearchResult]
    ):
        """잘못된 JSON 응답 시 원본 결과 반환"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [{"message": {"content": "이것은 JSON이 아닙니다"}}]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("쿼리", sample_results)

            # 파싱 실패해도 결과는 반환됨 (기본 순위 또는 원본)
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_general_exception_returns_original(
        self, sample_results: list[SearchResult]
    ):
        """일반 예외 시 원본 결과 반환"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = Exception("알 수 없는 에러")

            result = await reranker.rerank("쿼리", sample_results)

            # 일반 예외 시 원본 반환
            assert result == sample_results


class TestOpenRouterRerankerUtilities:
    """유틸리티 메서드 테스트"""

    def test_supports_caching_returns_true(self):
        """캐싱 지원 여부 - True 반환"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        assert reranker.supports_caching() is True

    def test_get_stats_initial(self):
        """초기 통계 값"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        reranker = OpenRouterReranker(api_key="test-key")
        stats = reranker.get_stats()

        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
        assert stats["model"] == "google/gemini-2.5-flash-lite"

    @pytest.mark.asyncio
    async def test_get_stats_after_success(self):
        """성공적인 요청 후 통계 업데이트"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        sample_results = [
            SearchResult(id="1", content="문서", score=0.5, metadata={})
        ]

        mock_response_data = {
            "choices": [
                {"message": {"content": '{"rankings": [{"index": 0, "score": 0.9}]}'}}
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            await reranker.rerank("쿼리", sample_results)

        stats = reranker.get_stats()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_get_stats_after_failure(self):
        """실패한 요청 후 통계 업데이트"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        sample_results = [
            SearchResult(id="1", content="문서", score=0.5, metadata={})
        ]

        reranker = OpenRouterReranker(api_key="test-key")

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timeout")

            await reranker.rerank("쿼리", sample_results)

        stats = reranker.get_stats()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.0


class TestOpenRouterRerankerScoreClamping:
    """점수 클램핑 테스트 (v1.2.1 버그 수정)"""

    @pytest.fixture
    def sample_results(self) -> list[SearchResult]:
        """테스트용 샘플 검색 결과"""
        return [
            SearchResult(id="1", content="문서 1 내용", score=0.8, metadata={}),
            SearchResult(id="2", content="문서 2 내용", score=0.6, metadata={}),
        ]

    @pytest.mark.asyncio
    async def test_score_clamping_above_1(self, sample_results: list[SearchResult]):
        """점수가 1.0 초과 시 1.0으로 클램핑"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        # LLM이 잘못된 점수(1.5)를 반환하는 경우
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 0, "score": 1.5}, {"index": 1, "score": 1.2}]}'
                    }
                }
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # 점수가 1.0으로 클램핑되어야 함
            assert result[0].score == 1.0
            assert result[1].score == 1.0

    @pytest.mark.asyncio
    async def test_score_clamping_below_0(self, sample_results: list[SearchResult]):
        """점수가 0.0 미만 시 0.0으로 클램핑"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        # LLM이 음수 점수를 반환하는 경우
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 0, "score": -0.5}, {"index": 1, "score": -1.0}]}'
                    }
                }
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # 점수가 0.0으로 클램핑되어야 함
            assert result[0].score == 0.0
            assert result[1].score == 0.0

    @pytest.mark.asyncio
    async def test_score_within_range_unchanged(
        self, sample_results: list[SearchResult]
    ):
        """정상 범위(0~1) 점수는 변경 없음"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": '{"rankings": [{"index": 0, "score": 0.85}, {"index": 1, "score": 0.45}]}'
                    }
                }
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # 정상 범위 점수는 그대로 유지
            assert result[0].score == 0.85
            assert result[1].score == 0.45


class TestOpenRouterRerankerMetadata:
    """메타데이터 테스트 (v1.2.1 개선)"""

    @pytest.fixture
    def sample_results(self) -> list[SearchResult]:
        """테스트용 샘플 검색 결과"""
        return [
            SearchResult(
                id="1", content="문서 1 내용", score=0.8, metadata={"source": "test"}
            ),
        ]

    @pytest.mark.asyncio
    async def test_metadata_includes_rerank_method(
        self, sample_results: list[SearchResult]
    ):
        """메타데이터에 rerank_method 포함"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {"message": {"content": '{"rankings": [{"index": 0, "score": 0.9}]}'}}
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key", model="anthropic/claude-3-haiku")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # rerank_method 메타데이터 확인
            assert "rerank_method" in result[0].metadata
            assert result[0].metadata["rerank_method"] == "openrouter:anthropic/claude-3-haiku"

    @pytest.mark.asyncio
    async def test_metadata_includes_original_score(
        self, sample_results: list[SearchResult]
    ):
        """메타데이터에 original_score 포함"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {"message": {"content": '{"rankings": [{"index": 0, "score": 0.95}]}'}}
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # original_score 메타데이터 확인 (원본 점수 0.8)
            assert "original_score" in result[0].metadata
            assert result[0].metadata["original_score"] == 0.8

    @pytest.mark.asyncio
    async def test_metadata_preserves_original(
        self, sample_results: list[SearchResult]
    ):
        """기존 메타데이터 보존"""
        from app.modules.core.retrieval.rerankers.openrouter_reranker import (
            OpenRouterReranker,
        )

        mock_response_data = {
            "choices": [
                {"message": {"content": '{"rankings": [{"index": 0, "score": 0.9}]}'}}
            ]
        }

        reranker = OpenRouterReranker(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            reranker.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await reranker.rerank("테스트 쿼리", sample_results)

            # 기존 메타데이터 보존 확인
            assert result[0].metadata["source"] == "test"
