"""
평가 시스템 인터페이스 정의 (Protocol 기반)

Protocol을 사용한 구조적 서브타이핑(structural subtyping) 인터페이스.
runtime_checkable 데코레이터로 isinstance() 검사 가능.

주요 인터페이스:
- IEvaluator: 답변 품질 평가기 프로토콜

의존성:
- models.py (EvaluationResult)
"""
from typing import Any, Protocol, runtime_checkable

from .models import EvaluationResult


@runtime_checkable
class IEvaluator(Protocol):
    """
    평가기 인터페이스 (Protocol)

    LLM 답변 품질을 평가하는 컴포넌트의 인터페이스.
    구조적 서브타이핑을 사용하여 명시적 상속 없이도 프로토콜 준수 가능.

    구현체 예시:
        - LLMBasedEvaluator: LLM을 사용한 평가
        - RagasEvaluator: RAGAS 라이브러리 기반 평가
        - HybridEvaluator: 여러 평가기 조합

    사용 예시:
        ```python
        def evaluate_answer(evaluator: IEvaluator, ...):
            result = await evaluator.evaluate(query, answer, context)
            if result.is_acceptable():
                return answer
        ```
    """

    @property
    def name(self) -> str:
        """
        평가기 이름

        Returns:
            평가기 식별 문자열 (예: "ragas", "llm_judge", "hybrid")
        """
        ...

    async def evaluate(
        self,
        query: str,
        answer: str,
        context: list[str],
        reference: str | None = None,
    ) -> EvaluationResult:
        """
        단일 답변 품질 평가

        Args:
            query: 사용자 질문
            answer: LLM이 생성한 답변
            context: 검색된 컨텍스트 문서 리스트
            reference: 참조 답변 (선택, ground truth)

        Returns:
            EvaluationResult: 평가 결과 (faithfulness, relevance, overall 등)

        Raises:
            EvaluationError: 평가 중 오류 발생 시
        """
        ...

    async def batch_evaluate(
        self,
        samples: list[dict[str, Any]],
    ) -> list[EvaluationResult]:
        """
        배치 평가

        여러 샘플을 한 번에 평가. 대규모 평가 시 효율적.

        Args:
            samples: 평가 샘플 리스트
                각 샘플은 {"query": str, "answer": str, "context": list[str]} 형식

        Returns:
            list[EvaluationResult]: 각 샘플에 대한 평가 결과 리스트

        Raises:
            EvaluationError: 평가 중 오류 발생 시
        """
        ...

    def is_available(self) -> bool:
        """
        평가기 사용 가능 여부 확인

        API 키 설정, 서비스 상태 등을 확인하여
        평가기가 실제로 사용 가능한지 반환.

        Returns:
            True: 평가 가능
            False: 평가 불가 (API 키 미설정, 서비스 다운 등)
        """
        ...


@runtime_checkable
class IFeedbackStore(Protocol):
    """
    피드백 저장소 인터페이스 (Protocol)

    사용자 피드백을 저장하고 조회하는 컴포넌트의 인터페이스.

    구현체 예시:
        - MongoDBFeedbackStore: MongoDB 기반 저장소
        - PostgreSQLFeedbackStore: PostgreSQL 기반 저장소
        - InMemoryFeedbackStore: 테스트용 인메모리 저장소
    """

    async def save(self, feedback: "FeedbackData") -> str:
        """
        피드백 저장

        Args:
            feedback: 저장할 피드백 데이터

        Returns:
            저장된 피드백의 ID
        """
        ...

    async def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list["FeedbackData"]:
        """
        세션별 피드백 조회

        Args:
            session_id: 세션 식별자
            limit: 최대 조회 개수

        Returns:
            해당 세션의 피드백 리스트
        """
        ...

    async def get_statistics(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        피드백 통계 조회

        Args:
            start_date: 시작일 (ISO 형식)
            end_date: 종료일 (ISO 형식)

        Returns:
            통계 정보 (총 개수, 긍정/부정 비율 등)
        """
        ...


# 순환 참조 방지를 위한 타입 힌트 임포트
from .models import FeedbackData  # noqa: E402
