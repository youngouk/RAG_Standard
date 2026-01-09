"""
평가 시스템 데이터 모델

사용자 쿼리와 LLM 응답에 대한 평가를 저장하고 관리하는 모델
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationType(str, Enum):
    """평가 유형"""

    QUERY = "query"
    RESPONSE = "response"
    OVERALL = "overall"


class EvaluationBase(BaseModel):
    """평가 기본 모델"""

    session_id: str = Field(..., description="세션 고유 ID")
    message_id: str = Field(..., description="메시지 고유 ID")

    # 평가 대상 내용
    query: str = Field(..., description="사용자 쿼리")
    response: str = Field(..., description="LLM 응답")

    # 평가 점수 (1-5점 척도)
    query_score: int | None = Field(None, ge=1, le=5, description="쿼리 품질 점수 (1-5)")
    response_score: int | None = Field(None, ge=1, le=5, description="응답 품질 점수 (1-5)")
    overall_score: int | None = Field(None, ge=1, le=5, description="전체 만족도 점수 (1-5)")

    # 세부 평가 항목 (선택적)
    relevance_score: int | None = Field(None, ge=1, le=5, description="관련성 점수")
    accuracy_score: int | None = Field(None, ge=1, le=5, description="정확성 점수")
    completeness_score: int | None = Field(None, ge=1, le=5, description="완전성 점수")
    clarity_score: int | None = Field(None, ge=1, le=5, description="명확성 점수")

    # 텍스트 피드백
    feedback: str | None = Field(None, max_length=1000, description="텍스트 피드백")

    # 평가자 정보 (선택적)
    evaluator_id: str | None = Field(None, description="평가자 식별자")
    evaluator_type: str | None = Field(default="human", description="평가자 유형 (human/auto)")

    # 추가 메타데이터
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

    @field_validator(
        "query_score",
        "response_score",
        "overall_score",
        "relevance_score",
        "accuracy_score",
        "completeness_score",
        "clarity_score",
    )
    @classmethod
    def validate_scores(cls, v: int | None) -> int | None:
        """점수 유효성 검증 (1-5 범위)"""
        if v is not None and (v < 1 or v > 5):
            raise ValueError(f"점수는 1에서 5 사이여야 합니다. 입력값: {v}")
        return v


class EvaluationCreate(EvaluationBase):
    """평가 생성 모델"""

    pass


class EvaluationUpdate(BaseModel):
    """평가 업데이트 모델"""

    query_score: int | None = Field(None, ge=1, le=5)
    response_score: int | None = Field(None, ge=1, le=5)
    overall_score: int | None = Field(None, ge=1, le=5)
    relevance_score: int | None = Field(None, ge=1, le=5)
    accuracy_score: int | None = Field(None, ge=1, le=5)
    completeness_score: int | None = Field(None, ge=1, le=5)
    clarity_score: int | None = Field(None, ge=1, le=5)
    feedback: str | None = Field(None, max_length=1000)
    metadata: dict[str, Any] | None = None


class Evaluation(EvaluationBase):
    """평가 전체 모델 (저장용)"""

    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str = Field(default_factory=lambda: str(uuid4()), description="평가 고유 ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="평가 생성 시간")
    updated_at: datetime | None = Field(None, description="평가 수정 시간")

    def update(self, update_data: EvaluationUpdate) -> None:
        """평가 정보 업데이트"""
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(self, field, value)
        self.updated_at = datetime.utcnow()

    def calculate_average_score(self) -> float | None:
        """평균 점수 계산"""
        scores = [
            self.query_score,
            self.response_score,
            self.overall_score,
            self.relevance_score,
            self.accuracy_score,
            self.completeness_score,
            self.clarity_score,
        ]
        valid_scores = [s for s in scores if s is not None]
        if valid_scores:
            return sum(valid_scores) / len(valid_scores)
        return None


class EvaluationResponse(Evaluation):
    """평가 응답 모델 (API 응답용)"""

    average_score: float | None = Field(None, description="평균 점수")

    def __init__(self, **data):
        super().__init__(**data)
        self.average_score = self.calculate_average_score()


class EvaluationListResponse(BaseModel):
    """평가 목록 응답 모델"""

    evaluations: list[EvaluationResponse]
    total: int
    page: int = 1
    page_size: int = 20


class EvaluationStatistics(BaseModel):
    """평가 통계 모델"""

    total_evaluations: int = Field(0, description="전체 평가 수")

    # 평균 점수
    average_query_score: float | None = Field(None, description="평균 쿼리 점수")
    average_response_score: float | None = Field(None, description="평균 응답 점수")
    average_overall_score: float | None = Field(None, description="평균 전체 점수")

    # 세부 평균 점수
    average_relevance_score: float | None = Field(None, description="평균 관련성 점수")
    average_accuracy_score: float | None = Field(None, description="평균 정확성 점수")
    average_completeness_score: float | None = Field(None, description="평균 완전성 점수")
    average_clarity_score: float | None = Field(None, description="평균 명확성 점수")

    # 점수 분포
    score_distribution: dict[str, dict[int, int]] = Field(
        default_factory=dict, description="점수 분포 (예: {'query_score': {1: 5, 2: 10, ...}})"
    )

    # 피드백 정보
    feedback_count: int = Field(0, description="피드백이 있는 평가 수")
    feedback_rate: float = Field(0.0, description="피드백 비율")

    # 시간 정보
    last_evaluation_at: datetime | None = Field(None, description="마지막 평가 시간")
    evaluations_today: int = Field(0, description="오늘 평가 수")
    evaluations_this_week: int = Field(0, description="이번 주 평가 수")
    evaluations_this_month: int = Field(0, description="이번 달 평가 수")

    # 세션별 통계
    unique_sessions: int = Field(0, description="평가된 고유 세션 수")
    average_evaluations_per_session: float = Field(0.0, description="세션당 평균 평가 수")


class EvaluationFilter(BaseModel):
    """평가 필터 모델"""

    session_id: str | None = None
    evaluator_id: str | None = None
    min_score: int | None = Field(None, ge=1, le=5)
    max_score: int | None = Field(None, ge=1, le=5)
    start_date: datetime | None = None
    end_date: datetime | None = None
    has_feedback: bool | None = None
    evaluation_type: EvaluationType | None = None
