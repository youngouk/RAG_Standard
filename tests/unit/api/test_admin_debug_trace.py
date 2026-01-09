import pytest

from app.api.schemas.debug import (
    DebugTrace,
    QueryTransformation,
    RetrievedDocument,
    SelfRAGEvaluation,
)


@pytest.mark.unit
class TestDebugTraceSchema:
    """디버깅 추적 데이터 모델 테스트"""

    def test_query_transformation_schema(self):
        """쿼리 변환 스키마 검증"""
        data = {
            "original": "강남 맛집",
            "expanded": "강남 맛집 OR 서울 강남구 음식점",
            "final_query": "강남 맛집 -광고"
        }

        transform = QueryTransformation(**data)

        assert transform.original == "강남 맛집"
        assert transform.expanded == "강남 맛집 OR 서울 강남구 음식점"
        assert transform.final_query == "강남 맛집 -광고"

    def test_retrieved_document_schema(self):
        """검색 문서 스키마 검증"""
        data = {
            "id": "doc-123",
            "title": "강남 맛집 TOP 10",
            "chunk_text": "강남역 근처에 위치한...",
            "vector_score": 0.92,
            "bm25_score": 0.78,
            "rerank_score": 0.95,
            "used_in_answer": True
        }

        doc = RetrievedDocument(**data)

        assert doc.id == "doc-123"
        assert doc.vector_score == 0.92
        assert doc.rerank_score == 0.95
        assert doc.used_in_answer is True

    def test_self_rag_evaluation_schema(self):
        """Self-RAG 평가 스키마 검증"""
        data = {
            "initial_quality": 0.73,
            "regenerated": True,
            "final_quality": 0.89,
            "reason": "초기 답변이 문서 근거 부족"
        }

        eval_result = SelfRAGEvaluation(**data)

        assert eval_result.initial_quality == 0.73
        assert eval_result.regenerated is True
        assert eval_result.final_quality == 0.89

    def test_debug_trace_complete_schema(self):
        """전체 디버깅 추적 스키마 검증"""
        data = {
            "query_transformation": {
                "original": "강남 맛집",
                "expanded": "강남 맛집 OR 서울 강남구 음식점",
                "final_query": "강남 맛집 -광고"
            },
            "retrieved_documents": [
                {
                    "id": "doc-123",
                    "title": "강남 맛집 TOP 10",
                    "chunk_text": "강남역 근처...",
                    "vector_score": 0.92,
                    "bm25_score": 0.78,
                    "rerank_score": 0.95,
                    "used_in_answer": True
                }
            ],
            "self_rag_evaluation": {
                "initial_quality": 0.73,
                "regenerated": True,
                "final_quality": 0.89,
                "reason": "초기 답변이 문서 근거 부족"
            },
            "generation_prompt": "다음 문서들을 참고하여..."
        }

        trace = DebugTrace(**data)

        assert trace.query_transformation.original == "강남 맛집"
        assert len(trace.retrieved_documents) == 1
        assert trace.self_rag_evaluation.regenerated is True
