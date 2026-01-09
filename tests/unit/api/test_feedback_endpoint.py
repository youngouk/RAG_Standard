"""
피드백 API 엔드포인트 테스트
POST /api/chat/feedback 엔드포인트 검증
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestFeedbackSchema:
    """피드백 스키마 테스트"""

    def test_feedback_request_valid(self):
        """유효한 피드백 요청 생성"""
        from app.api.schemas.feedback import FeedbackRequest

        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
        )

        assert request.session_id == "session-123"
        assert request.message_id == "msg-456"
        assert request.rating == 1
        assert request.comment is None

    def test_feedback_request_with_comment(self):
        """코멘트 포함 피드백 요청"""
        from app.api.schemas.feedback import FeedbackRequest

        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=-1,
            comment="답변이 정확하지 않았습니다",
        )

        assert request.comment == "답변이 정확하지 않았습니다"
        assert request.rating == -1

    def test_feedback_request_with_query_response(self):
        """쿼리와 응답 포함 피드백 요청"""
        from app.api.schemas.feedback import FeedbackRequest

        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            query="서울 맛집 추천해줘",
            response="서울에 위치한 맛집 3곳을 추천드립니다...",
        )

        assert request.query == "서울 맛집 추천해줘"
        assert request.response is not None

    def test_feedback_request_invalid_rating(self):
        """잘못된 평점 (1, -1 이외의 값)"""
        from pydantic import ValidationError

        from app.api.schemas.feedback import FeedbackRequest

        with pytest.raises(ValidationError):
            FeedbackRequest(
                session_id="session-123",
                message_id="msg-456",
                rating=0,  # 0은 허용되지 않음
            )

    def test_feedback_request_invalid_rating_out_of_range(self):
        """범위 밖의 평점"""
        from pydantic import ValidationError

        from app.api.schemas.feedback import FeedbackRequest

        with pytest.raises(ValidationError):
            FeedbackRequest(
                session_id="session-123",
                message_id="msg-456",
                rating=5,  # 5는 허용되지 않음
            )

    def test_feedback_response_success(self):
        """성공 응답 생성"""
        from app.api.schemas.feedback import FeedbackResponse

        response = FeedbackResponse(
            success=True,
            feedback_id="fb-789",
            message="피드백이 저장되었습니다",
            golden_candidate=False,
        )

        assert response.success is True
        assert response.feedback_id == "fb-789"
        assert response.golden_candidate is False

    def test_feedback_response_golden_candidate(self):
        """Golden Dataset 후보로 등록된 응답"""
        from app.api.schemas.feedback import FeedbackResponse

        response = FeedbackResponse(
            success=True,
            feedback_id="fb-789",
            message="피드백이 저장되었습니다. Golden Dataset 후보로 등록되었습니다.",
            golden_candidate=True,
        )

        assert response.golden_candidate is True

    def test_feedback_response_failure(self):
        """실패 응답 생성"""
        from app.api.schemas.feedback import FeedbackResponse

        response = FeedbackResponse(
            success=False,
            feedback_id=None,
            message="피드백 저장에 실패했습니다",
            golden_candidate=False,
        )

        assert response.success is False
        assert response.feedback_id is None


class TestFeedbackEndpoint:
    """피드백 엔드포인트 통합 테스트"""

    @pytest.fixture
    def mock_feedback_service(self):
        """피드백 서비스 Mock"""
        service = MagicMock()
        service.save_feedback = AsyncMock(
            return_value={
                "feedback_id": "fb-123",
                "golden_candidate": False,
            }
        )
        return service

    def test_feedback_endpoint_exists(self):
        """피드백 엔드포인트가 chat_router에 등록되어 있는지 확인"""
        from app.api.routers.chat_router import router

        # 라우터에 등록된 경로 확인
        routes = [route.path for route in router.routes]
        assert "/feedback" in routes or "/chat/feedback" in routes or any(
            "feedback" in route for route in routes
        )

    @pytest.mark.asyncio
    async def test_process_feedback_function_exists(self):
        """process_feedback 함수 존재 확인"""
        # chat_router 모듈에서 함수 직접 확인
        from app.api.routers.chat_router import process_feedback

        assert callable(process_feedback)


class TestFeedbackData:
    """FeedbackData 모델 테스트 (저장용)"""

    def test_feedback_data_from_request(self):
        """FeedbackRequest에서 FeedbackData 변환"""
        from app.api.schemas.feedback import FeedbackRequest
        from app.modules.core.evaluation.models import FeedbackData

        request = FeedbackRequest(
            session_id="session-123",
            message_id="msg-456",
            rating=1,
            comment="좋은 답변이었습니다",
            query="질문 내용",
            response="답변 내용",
        )

        # FeedbackData로 변환
        feedback_data = FeedbackData(
            session_id=request.session_id,
            message_id=request.message_id,
            rating=request.rating,
            comment=request.comment,
            query=request.query,
            response=request.response,
        )

        assert feedback_data.session_id == "session-123"
        assert feedback_data.rating == 1
        assert feedback_data.is_positive is True

    def test_feedback_data_negative_rating(self):
        """부정적 평점 피드백"""
        from app.modules.core.evaluation.models import FeedbackData

        feedback_data = FeedbackData(
            session_id="session-123",
            message_id="msg-456",
            rating=-1,
        )

        assert feedback_data.is_positive is False
