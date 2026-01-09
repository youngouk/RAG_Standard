"""
평가 API 스키마
관리자용 배치 평가 API의 Pydantic 모델

주요 스키마:
- BatchEvaluateRequest: 배치 평가 요청
- BatchEvaluateResponse: 배치 평가 응답
- EvaluationSampleSchema: 개별 평가 샘플
"""

from pydantic import BaseModel, Field


class EvaluationSampleSchema(BaseModel):
    """
    평가 샘플 스키마

    단일 평가 대상 (질문-답변-컨텍스트 쌍)
    """

    query: str = Field(
        ...,
        description="사용자 질문",
        examples=["서울 맛집 추천해줘"],
    )
    answer: str = Field(
        ...,
        description="생성된 답변",
        examples=["서울에 위치한 맛집 3곳을 추천드립니다..."],
    )
    context: str = Field(
        ...,
        description="검색된 컨텍스트",
        examples=["A식당: 강남역 3번 출구..."],
    )
    reference: str | None = Field(
        default=None,
        description="참조 정답 (선택, Golden Dataset용)",
        examples=["서울에는 A, B, C 식당이 있습니다..."],
    )


class EvaluationResultSchema(BaseModel):
    """
    개별 평가 결과 스키마
    """

    faithfulness: float = Field(
        ...,
        description="충실도 점수 (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    relevance: float = Field(
        ...,
        description="관련성 점수 (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    overall: float = Field(
        ...,
        description="종합 점수 (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        default="",
        description="평가 근거 설명",
    )
    context_precision: float | None = Field(
        default=None,
        description="컨텍스트 정밀도 (Ragas 전용)",
    )


class BatchEvaluateRequest(BaseModel):
    """
    배치 평가 요청 스키마

    여러 샘플을 한 번에 평가 요청
    """

    samples: list[EvaluationSampleSchema] = Field(
        ...,
        description="평가할 샘플 리스트",
        min_length=1,
        max_length=100,
    )
    provider: str = Field(
        default="internal",
        description="평가기 종류: 'internal' (빠름) 또는 'ragas' (정밀)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "samples": [
                        {
                            "query": "서울 맛집 추천해줘",
                            "answer": "서울에 위치한 맛집 3곳을 추천드립니다...",
                            "context": "A식당: 강남역 3번 출구...",
                        }
                    ],
                    "provider": "internal",
                }
            ]
        }
    }


class BatchEvaluateResponse(BaseModel):
    """
    배치 평가 응답 스키마
    """

    success: bool = Field(
        ...,
        description="평가 성공 여부",
    )
    results: list[EvaluationResultSchema] = Field(
        default_factory=list,
        description="개별 평가 결과 리스트",
    )
    summary: dict = Field(
        default_factory=dict,
        description="요약 통계 (평균 점수 등)",
    )
    provider: str = Field(
        ...,
        description="사용된 평가기 종류",
    )
    sample_count: int = Field(
        ...,
        description="평가된 샘플 수",
    )
    message: str = Field(
        default="",
        description="결과 메시지",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "results": [
                        {
                            "faithfulness": 0.85,
                            "relevance": 0.90,
                            "overall": 0.875,
                            "reasoning": "답변이 컨텍스트에 충실함",
                        }
                    ],
                    "summary": {
                        "avg_faithfulness": 0.85,
                        "avg_relevance": 0.90,
                        "avg_overall": 0.875,
                    },
                    "provider": "internal",
                    "sample_count": 1,
                    "message": "평가 완료",
                }
            ]
        }
    }
