"""
디버깅 API 스키마 - Admin 전용

RAG 파이프라인의 중간 단계 추적 정보를 제공합니다.
"""

from pydantic import BaseModel, Field


class QueryTransformation(BaseModel):
    """쿼리 변환 로그"""

    original: str = Field(..., description="원본 쿼리")
    expanded: str | None = Field(None, description="확장된 쿼리")
    final_query: str = Field(..., description="최종 실행 쿼리")


class RetrievedDocument(BaseModel):
    """검색된 문서 정보"""

    id: str = Field(..., description="문서 ID")
    title: str = Field(..., description="문서 제목")
    chunk_text: str = Field(..., description="청크 텍스트")

    # 점수들
    vector_score: float = Field(..., description="벡터 검색 점수")
    bm25_score: float | None = Field(None, description="BM25 점수")
    rerank_score: float | None = Field(None, description="리랭킹 점수")

    # 사용 여부
    used_in_answer: bool = Field(..., description="답변 생성에 사용됨")


class SelfRAGEvaluation(BaseModel):
    """Self-RAG 평가 결과"""

    initial_quality: float = Field(..., description="초기 품질 점수")
    regenerated: bool = Field(..., description="재생성 여부")
    final_quality: float = Field(..., description="최종 품질 점수")
    reason: str | None = Field(None, description="평가 사유")


class DebugTrace(BaseModel):
    """디버깅 추적 정보 - 전체"""

    query_transformation: QueryTransformation
    retrieved_documents: list[RetrievedDocument]
    self_rag_evaluation: SelfRAGEvaluation | None = None
    generation_prompt: str | None = Field(None, description="생성 프롬프트")
