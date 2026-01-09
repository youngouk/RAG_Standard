"""
OpenAI/OpenRouter Embedding 구현체

OpenAI Embedding API 또는 OpenRouter를 통한 임베딩 생성
text-embedding-3-large 모델로 3072차원 벡터 생성 (이미 정규화됨)

OpenRouter 지원 임베딩 모델:
- openai/text-embedding-3-small
- openai/text-embedding-3-large
- qwen/qwen3-embedding-8b
- google/embedding-001
- intfloat/e5-large-v2
"""

import asyncio
import os

import numpy as np
from langchain.embeddings.base import Embeddings
from openai import OpenAI

from ....lib.logger import get_logger
from .interfaces import BaseEmbedder

logger = get_logger(__name__)

# OpenRouter API 기본 URL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenAIEmbedder(BaseEmbedder, Embeddings):
    """
    OpenAI Embedding 모델 래퍼

    BaseEmbedder와 LangChain Embeddings를 모두 구현하여
    기존 코드와의 호환성 유지 및 확장 가능성 확보
    """

    def __init__(
        self,
        openai_api_key: str,
        model_name: str = "text-embedding-3-large",
        output_dimensionality: int = 3072,
        batch_size: int = 100,
    ):
        """
        OpenAI Embedder 초기화

        Args:
            openai_api_key: OpenAI API 키
            model_name: 모델 이름 (기본: text-embedding-3-large)
            output_dimensionality: 출력 차원 (기본: 3072)
            batch_size: 배치 임베딩 생성 시 배치 크기
        """
        # BaseEmbedder 초기화
        super().__init__(
            model_name=model_name,
            output_dimensionality=output_dimensionality,
            api_key=openai_api_key,
        )

        # OpenAI 클라이언트 초기화 (Phase 1 MVP: API 키 없으면 graceful degradation)
        self.client = None
        if openai_api_key:
            try:
                self.client = OpenAI(api_key=openai_api_key)
                logger.info(
                    f"✅ Initialized OpenAIEmbedder: model={model_name}, dim={output_dimensionality}"
                )
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize OpenAI client: {str(e)}")
        else:
            logger.warning(
                "⚠️  OpenAI API key not provided. OpenAI embedder will be unavailable in Phase 1 MVP."
            )

        self.batch_size = batch_size

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        """
        L2 정규화 수행 (선택적)

        OpenAI는 이미 정규화된 벡터를 반환하지만, 안전을 위해 확인 및 정규화 수행

        Args:
            vector: 정규화할 벡터

        Returns:
            L2 정규화된 벡터
        """
        arr = np.array(vector)
        norm = np.linalg.norm(arr)

        if norm > 0:
            # 이미 정규화되어 있는지 확인 (허용 오차 0.01)
            if abs(norm - 1.0) < 0.01:
                return vector  # 이미 정규화됨

            # 정규화 필요
            normalized = arr / norm
            return normalized.tolist()  # type: ignore[no-any-return]

        logger.warning("Zero norm vector encountered, returning as-is")
        return vector

    def _batch_embed(self, texts: list[str]) -> list[list[float]]:
        """
        배치 단위로 임베딩 생성 (동기 버전)

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            정규화된 임베딩 벡터 리스트
        """
        # Phase 1 MVP: OpenAI API 키 없으면 빈 임베딩 반환
        if not self.client:
            logger.warning("⚠️  OpenAI client unavailable. Returning zero embeddings.")
            return [[0.0] * self.output_dimensionality for _ in texts]

        embeddings = []

        # 배치 처리
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            try:
                # OpenAI API 호출
                response = self.client.embeddings.create(  # type: ignore[union-attr,arg-type]
                    model=self.model_name,
                    input=batch,
                    dimensions=self.output_dimensionality,
                )

                # 결과 파싱
                for item in response.data:
                    embedding = item.embedding
                    # OpenAI는 이미 정규화된 벡터 반환하지만 확인
                    normalized = self._normalize_vector(embedding)
                    embeddings.append(normalized)

            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i//self.batch_size}: {e}")
                # 오류 발생 시 빈 벡터 추가
                for _ in batch:
                    embeddings.append([0.0] * self.output_dimensionality)

        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        문서 임베딩 생성

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            L2 정규화된 3072차원 임베딩 벡터 리스트
        """
        if not texts:
            return []

        logger.info(f"Embedding {len(texts)} documents")

        # 배치 처리로 임베딩 생성
        embeddings = self._batch_embed(texts)

        logger.info(f"Generated {len(embeddings)} document embeddings")
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """
        쿼리 임베딩 생성

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            L2 정규화된 3072차원 임베딩 벡터
        """
        logger.debug("Embedding query")

        try:
            # 단일 쿼리 임베딩
            response = self.client.embeddings.create(  # type: ignore[union-attr]
                model=self.model_name,
                input=text,
                dimensions=self.output_dimensionality,
            )

            # 결과 파싱
            embedding = response.data[0].embedding
            normalized = self._normalize_vector(embedding)

            # 차원 확인
            if len(normalized) != self.output_dimensionality:
                logger.warning(
                    f"Unexpected embedding dimension: {len(normalized)} != {self.output_dimensionality}"
                )

            return normalized

        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            # 오류 발생 시 영벡터 반환
            return [0.0] * self.output_dimensionality

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        비동기 문서 임베딩 생성

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            L2 정규화된 3072차원 임베딩 벡터 리스트
        """
        # 동기 메서드를 비동기로 실행
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        """
        비동기 쿼리 임베딩 생성

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            L2 정규화된 3072차원 임베딩 벡터
        """
        # 동기 메서드를 비동기로 실행
        return await asyncio.to_thread(self.embed_query, text)

    def validate_embedding(self, embedding: list[float]) -> bool:
        """
        임베딩 벡터 검증

        Args:
            embedding: 검증할 임베딩 벡터

        Returns:
            검증 성공 여부
        """
        # 차원 확인
        if not self._validate_dimension(embedding):
            logger.error(f"Invalid dimension: {len(embedding)} != {self.output_dimensionality}")
            return False

        # L2 norm 확인 (정규화 여부)
        norm = np.linalg.norm(np.array(embedding))
        if abs(norm - 1.0) > 0.01:  # 허용 오차
            logger.warning(f"Vector not normalized: norm={norm}")
            return False

        return True


class OpenRouterEmbedder(BaseEmbedder, Embeddings):
    """
    OpenRouter Embedding 모델 래퍼

    OpenRouter의 /api/v1/embeddings 엔드포인트를 통해 임베딩 생성
    OpenAI SDK와 100% 호환되며 base_url만 변경하여 사용

    지원 모델:
    - google/gemini-embedding-001 (3072차원, dimensions 파라미터 미지원, 한국어 최적화)
    - openai/text-embedding-3-large (3072차원, dimensions 파라미터 지원)
    - openai/text-embedding-3-small (1536차원, dimensions 파라미터 지원)
    - qwen/qwen3-embedding-8b
    - intfloat/e5-large-v2

    참고: https://openrouter.ai/models?q=embedding

    Note:
        - OpenAI 모델만 dimensions 파라미터 지원
        - Gemini 모델은 기본 3072차원 출력 (MRL 기법으로 768/1536/3072 지원)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "openai/text-embedding-3-large",
        output_dimensionality: int = 3072,
        batch_size: int = 100,
        site_url: str = "",
        app_name: str = "RAG-Chatbot",
    ):
        """
        OpenRouter Embedder 초기화

        Args:
            api_key: OpenRouter API 키 (없으면 환경변수 OPENROUTER_API_KEY 사용)
            model_name: 모델 이름 (OpenRouter 형식: provider/model-name)
            output_dimensionality: 출력 차원 (기본: 3072)
            batch_size: 배치 임베딩 생성 시 배치 크기
            site_url: OpenRouter 권장 헤더 - 사이트 URL
            app_name: OpenRouter 권장 헤더 - 앱 이름
        """
        # BaseEmbedder 초기화
        super().__init__(
            model_name=model_name,
            output_dimensionality=output_dimensionality,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY", ""),
        )

        # OpenRouter API 키 확인
        resolved_api_key = api_key or os.getenv("OPENROUTER_API_KEY")

        # OpenRouter 클라이언트 초기화
        self.client = None
        if resolved_api_key:
            try:
                self.client = OpenAI(
                    base_url=OPENROUTER_BASE_URL,
                    api_key=resolved_api_key,
                    default_headers={
                        "HTTP-Referer": site_url,
                        "X-Title": app_name,
                    },
                )
                logger.info(
                    f"✅ Initialized OpenRouterEmbedder: model={model_name}, dim={output_dimensionality}"
                )
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize OpenRouter client: {str(e)}")
        else:
            logger.warning(
                "⚠️  OpenRouter API key not provided. OpenRouter embedder will be unavailable."
            )

        self.batch_size = batch_size

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        """
        L2 정규화 수행 (선택적)

        Args:
            vector: 정규화할 벡터

        Returns:
            L2 정규화된 벡터
        """
        arr = np.array(vector)
        norm = np.linalg.norm(arr)

        if norm > 0:
            # 이미 정규화되어 있는지 확인 (허용 오차 0.01)
            if abs(norm - 1.0) < 0.01:
                return vector  # 이미 정규화됨

            # 정규화 필요
            normalized = arr / norm
            return normalized.tolist()  # type: ignore[no-any-return]

        logger.warning("Zero norm vector encountered, returning as-is")
        return vector

    def _batch_embed(self, texts: list[str]) -> list[list[float]]:
        """
        배치 단위로 임베딩 생성 (동기 버전)

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            정규화된 임베딩 벡터 리스트
        """
        if not self.client:
            logger.warning("⚠️  OpenRouter client unavailable. Returning zero embeddings.")
            return [[0.0] * self.output_dimensionality for _ in texts]

        embeddings = []

        # 배치 처리
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            try:
                # OpenRouter Embeddings API 호출
                response = self.client.embeddings.create(  # type: ignore[union-attr,arg-type]
                    model=self.model_name,
                    input=batch,
                    # dimensions 파라미터는 일부 모델만 지원
                    # OpenAI 모델은 지원, 다른 모델은 기본 차원 사용
                    **(
                        {"dimensions": self.output_dimensionality}  # type: ignore[arg-type]
                        if "openai/" in self.model_name
                        else {}
                    ),
                )

                # 결과 파싱
                for item in response.data:
                    embedding = item.embedding
                    normalized = self._normalize_vector(embedding)
                    embeddings.append(normalized)

            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i//self.batch_size}: {e}")
                # 오류 발생 시 빈 벡터 추가
                for _ in batch:
                    embeddings.append([0.0] * self.output_dimensionality)

        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        문서 임베딩 생성

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            L2 정규화된 임베딩 벡터 리스트
        """
        if not texts:
            return []

        logger.info(f"🌐 OpenRouter embedding {len(texts)} documents")

        embeddings = self._batch_embed(texts)

        logger.info(f"✅ Generated {len(embeddings)} document embeddings via OpenRouter")
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """
        쿼리 임베딩 생성

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            L2 정규화된 임베딩 벡터
        """
        if not self.client:
            logger.warning("⚠️  OpenRouter client unavailable. Returning zero embedding.")
            return [0.0] * self.output_dimensionality

        logger.debug("🌐 OpenRouter embedding query")

        try:
            # OpenRouter Embeddings API 호출
            response = self.client.embeddings.create(  # type: ignore[union-attr,arg-type]
                model=self.model_name,
                input=text,
                **(
                    {"dimensions": self.output_dimensionality}  # type: ignore[arg-type]
                    if "openai/" in self.model_name
                    else {}
                ),
            )

            embedding = response.data[0].embedding
            normalized = self._normalize_vector(embedding)

            # 차원 확인
            if len(normalized) != self.output_dimensionality:
                logger.warning(
                    f"Unexpected embedding dimension: {len(normalized)} != {self.output_dimensionality}"
                )

            return normalized

        except Exception as e:
            logger.error(f"Error generating query embedding via OpenRouter: {e}")
            return [0.0] * self.output_dimensionality

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        비동기 문서 임베딩 생성

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            L2 정규화된 임베딩 벡터 리스트
        """
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        """
        비동기 쿼리 임베딩 생성

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            L2 정규화된 임베딩 벡터
        """
        return await asyncio.to_thread(self.embed_query, text)

    def validate_embedding(self, embedding: list[float]) -> bool:
        """
        임베딩 벡터 검증

        Args:
            embedding: 검증할 임베딩 벡터

        Returns:
            검증 성공 여부
        """
        # 차원 확인
        if not self._validate_dimension(embedding):
            logger.error(f"Invalid dimension: {len(embedding)} != {self.output_dimensionality}")
            return False

        # L2 norm 확인 (정규화 여부)
        norm = np.linalg.norm(np.array(embedding))
        if abs(norm - 1.0) > 0.01:  # 허용 오차
            logger.warning(f"Vector not normalized: norm={norm}")
            return False

        return True
