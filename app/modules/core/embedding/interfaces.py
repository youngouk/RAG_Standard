"""
Embedding Module - 인터페이스 정의

임베딩 모듈의 추상 인터페이스를 정의합니다.
다양한 임베딩 제공자(Gemini, OpenAI, Cohere 등)를 추상화하여 일관된 인터페이스 제공
"""

from abc import ABC, abstractmethod


class IEmbedder(ABC):
    """
    임베딩 생성기 인터페이스

    모든 임베딩 구현체는 이 인터페이스를 구현해야 합니다.
    LangChain Embeddings 인터페이스와 호환되도록 설계
    """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        문서 리스트에 대한 임베딩 벡터 생성 (RETRIEVAL_DOCUMENT 타입)

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            정규화된 임베딩 벡터 리스트 (각 벡터는 float 리스트)

        Raises:
            Exception: 임베딩 생성 실패 시
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """
        단일 쿼리에 대한 임베딩 벡터 생성 (RETRIEVAL_QUERY 타입)

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            정규화된 임베딩 벡터 (float 리스트)

        Raises:
            Exception: 임베딩 생성 실패 시
        """
        pass

    @abstractmethod
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        비동기 문서 임베딩 생성

        Args:
            texts: 임베딩할 문서 텍스트 리스트

        Returns:
            정규화된 임베딩 벡터 리스트

        Raises:
            Exception: 임베딩 생성 실패 시
        """
        pass

    @abstractmethod
    async def aembed_query(self, text: str) -> list[float]:
        """
        비동기 쿼리 임베딩 생성

        Args:
            text: 임베딩할 쿼리 텍스트

        Returns:
            정규화된 임베딩 벡터

        Raises:
            Exception: 임베딩 생성 실패 시
        """
        pass

    @abstractmethod
    def validate_embedding(self, embedding: list[float]) -> bool:
        """
        임베딩 벡터 검증

        임베딩 벡터가 올바른 차원과 정규화 상태인지 검증합니다.

        Args:
            embedding: 검증할 임베딩 벡터

        Returns:
            검증 성공 여부 (True: 유효, False: 무효)
        """
        pass

    @property
    @abstractmethod
    def output_dimensionality(self) -> int:
        """
        임베딩 벡터의 출력 차원수

        Returns:
            임베딩 벡터 차원 (예: 1536, 768, 3072)
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        사용 중인 임베딩 모델 이름

        Returns:
            모델 이름 (예: "models/gemini-embedding-001", "text-embedding-ada-002")
        """
        pass


class BaseEmbedder(IEmbedder):
    """
    임베딩 구현체의 기본 베이스 클래스

    공통 유틸리티 메서드를 제공하여 중복 코드 최소화
    구체 클래스는 이 클래스를 상속하여 추상 메서드만 구현
    """

    def __init__(
        self,
        model_name: str,
        output_dimensionality: int,
        api_key: str | None = None,
    ):
        """
        기본 초기화

        Args:
            model_name: 임베딩 모델 이름
            output_dimensionality: 출력 벡터 차원
            api_key: API 키 (선택적)
        """
        self._model_name = model_name
        self._output_dimensionality = output_dimensionality
        self._api_key = api_key

    @property
    def model_name(self) -> str:
        """사용 중인 임베딩 모델 이름"""
        return self._model_name

    @property
    def output_dimensionality(self) -> int:
        """임베딩 벡터의 출력 차원수"""
        return self._output_dimensionality

    def _validate_dimension(self, embedding: list[float]) -> bool:
        """
        임베딩 차원 검증 헬퍼 메서드

        Args:
            embedding: 검증할 임베딩 벡터

        Returns:
            차원이 일치하면 True, 아니면 False
        """
        return len(embedding) == self._output_dimensionality
