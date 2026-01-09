"""
평가 시스템 데이터 모델
평가 결과 및 피드백 데이터의 타입 정의.

주요 모델:
- EvaluationResult: LLM 답변 품질 평가 결과
- FeedbackData: 사용자 피드백 데이터

의존성: 없음 (순수 데이터 모델)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EvaluationResult:
    """
    평가 결과 모델

    LLM 답변의 품질을 다양한 지표로 평가한 결과를 담는 데이터 클래스.
    모든 점수는 0.0-1.0 범위로 정규화됨.

    Args:
        faithfulness: 답변이 컨텍스트에 얼마나 충실한지 (0.0-1.0)
        relevance: 답변이 질문에 얼마나 관련있는지 (0.0-1.0)
        overall: 종합 점수 (0.0-1.0)
        reasoning: 평가 근거 설명 (선택)
        context_precision: 컨텍스트 정밀도 (선택, 0.0-1.0)
        answer_similarity: 참조 답변과의 유사도 (선택, 0.0-1.0)
        raw_scores: 원본 평가 점수 (디버깅용)
        evaluated_at: 평가 시각

    Raises:
        ValueError: 점수가 0.0-1.0 범위를 벗어난 경우
    """
    faithfulness: float
    relevance: float
    overall: float
    reasoning: str = ""
    context_precision: float | None = None
    answer_similarity: float | None = None
    raw_scores: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """점수 범위 검증 (0.0-1.0)"""
        # 필수 점수 필드 검증
        for field_name in ["faithfulness", "relevance", "overall"]:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name}는 0.0-1.0 범위여야 합니다: {value}")

        # 선택 점수 필드 검증
        for field_name in ["context_precision", "answer_similarity"]:
            value = getattr(self, field_name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name}는 0.0-1.0 범위여야 합니다: {value}")

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (직렬화용)"""
        return {
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "overall": self.overall,
            "reasoning": self.reasoning,
            "context_precision": self.context_precision,
            "answer_similarity": self.answer_similarity,
            "raw_scores": self.raw_scores,
            "evaluated_at": self.evaluated_at.isoformat(),
        }

    def is_acceptable(self, threshold: float = 0.7) -> bool:
        """
        답변 품질이 허용 가능한지 확인

        Args:
            threshold: 최소 허용 점수 (기본값: 0.7)

        Returns:
            overall 점수가 threshold 이상이면 True
        """
        return self.overall >= threshold


@dataclass
class FeedbackData:
    """
    사용자 피드백 데이터 모델

    사용자가 제출한 답변 평가 피드백을 담는 데이터 클래스.
    rating은 1(긍정) 또는 -1(부정)만 허용.

    Args:
        session_id: 세션 식별자
        message_id: 메시지 식별자
        rating: 평가 점수 (1: 좋음, -1: 나쁨)
        comment: 사용자 코멘트 (선택)
        query: 원본 질문 (선택)
        response: 원본 답변 (선택)
        created_at: 피드백 생성 시각

    Raises:
        ValueError: rating이 1 또는 -1이 아닌 경우
    """
    session_id: str
    message_id: str
    rating: int
    comment: str = ""
    query: str | None = None
    response: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """rating 검증 (1 또는 -1만 허용)"""
        if self.rating not in (1, -1):
            raise ValueError(f"rating은 1 또는 -1이어야 합니다: {self.rating}")

    @property
    def is_positive(self) -> bool:
        """긍정적 피드백 여부"""
        return self.rating == 1

    @property
    def is_negative(self) -> bool:
        """부정적 피드백 여부"""
        return self.rating == -1

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (직렬화용)"""
        return {
            "session_id": self.session_id,
            "message_id": self.message_id,
            "rating": self.rating,
            "comment": self.comment,
            "query": self.query,
            "response": self.response,
            "created_at": self.created_at.isoformat(),
        }
