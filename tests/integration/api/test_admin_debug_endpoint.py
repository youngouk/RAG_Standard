"""
Admin 디버깅 API 통합 테스트

Task 5: 디버깅 API - Admin 엔드포인트 테스트
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.mark.integration
class TestAdminDebugEndpoint:
    """Admin 디버깅 API 통합 테스트"""

    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        return TestClient(app)

    def test_get_debug_trace_not_found(self, client):
        """
        존재하지 않는 메시지 조회

        Given: 존재하지 않는 message_id
        When: GET /admin/debug/...
        Then: 404 Not Found
        """
        response = client.get(
            "/admin/debug/session/invalid-session/messages/invalid-msg",
            headers={"Authorization": "Bearer admin-key"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.skip(reason="Admin 인증은 별도 구현 필요 (Phase 별도)")
    def test_get_debug_trace_unauthorized(self, client):
        """
        인증 실패 (TODO: Admin 인증 구현 후 활성화)

        Given: 잘못된 인증 키
        When: GET /admin/debug/...
        Then: 401 Unauthorized
        """
        response = client.get(
            "/admin/debug/session/test-session/messages/msg-123",
            headers={"Authorization": "Bearer wrong-key"},
        )

        assert response.status_code == 401
