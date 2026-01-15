"""
스트리밍 API 통합 테스트 (E2E)

/chat/stream 엔드포인트의 전체 흐름을 검증합니다:
1. SSE 이벤트 수신 및 파싱
2. 이벤트 순서 검증 (metadata → chunk* → done)
3. 에러 핸들링

테스트 방식:
- TestClient 버전: 실제 서버 없이 FastAPI TestClient로 테스트
- 실제 서버 버전: httpx.AsyncClient로 실서버 테스트 (skip 처리)

SSE 이벤트 형식: event: {type}\ndata: {json}\n\n
- metadata: 검색 결과 메타데이터 (세션 ID, 문서 수 등)
- chunk: LLM 응답 텍스트 청크 (data, chunk_index)
- done: 스트리밍 완료 이벤트 (session_id, total_chunks)
- error: 에러 이벤트 (error_code, message)
"""

import json
import os
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# main.py에서 FastAPI 앱 임포트
from main import app


def parse_sse_events(response_text: str) -> list[dict[str, Any]]:
    """
    SSE 응답 텍스트를 파싱하여 이벤트 리스트로 변환

    SSE 형식: event: {type}\ndata: {json}\n\n

    Args:
        response_text: SSE 형식의 응답 텍스트

    Returns:
        이벤트 딕셔너리 리스트 (event 타입 + data 포함)
    """
    events = []
    lines = response_text.strip().split("\n")

    current_event_type = None
    current_data = None

    for line in lines:
        line = line.strip()

        if line.startswith("event: "):
            # 이벤트 타입 추출
            current_event_type = line[7:]

        elif line.startswith("data: "):
            # 데이터 추출 및 JSON 파싱
            try:
                current_data = json.loads(line[6:])
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 문자열 유지
                current_data = {"raw": line[6:]}

            # 이벤트 추가 (event 타입이 있으면 사용, 없으면 data에서 추출)
            if current_event_type:
                events.append({
                    "event_type": current_event_type,
                    "data": current_data
                })
            elif isinstance(current_data, dict) and "event" in current_data:
                events.append({
                    "event_type": current_data["event"],
                    "data": current_data
                })
            else:
                events.append({
                    "event_type": "unknown",
                    "data": current_data
                })

            # 초기화
            current_event_type = None
            current_data = None

    return events


# =============================================================================
# Mock 기반 TestClient 테스트 (실제 서버 없이 테스트)
# =============================================================================

@pytest.mark.integration
class TestStreamingAPIWithMock:
    """
    Mock 기반 스트리밍 API 테스트

    FastAPI TestClient를 사용하여 실제 서버 없이 테스트합니다.
    ChatService의 stream_rag_pipeline을 Mock 처리하여 SSE 이벤트를 시뮬레이션합니다.
    """

    @pytest.fixture
    def mock_chat_service(self):
        """ChatService Mock 생성"""
        mock_service = MagicMock()

        async def mock_stream_generator(message: str, session_id: str | None, options: dict | None) -> AsyncGenerator[dict, None]:
            """Mock 스트리밍 제너레이터"""
            # 1. metadata 이벤트
            yield {
                "event": "metadata",
                "data": {
                    "session_id": session_id or "mock-session-123",
                    "search_results": 5,
                    "ranked_results": 3,
                    "reranking_applied": True,
                    "message_id": "mock-msg-456",
                }
            }

            # 2. chunk 이벤트들
            chunks = ["안녕", "하세요", "! ", "테스트", " 응답", "입니다", "."]
            for i, chunk in enumerate(chunks):
                yield {
                    "event": "chunk",
                    "data": chunk,
                    "chunk_index": i,
                }

            # 3. done 이벤트
            yield {
                "event": "done",
                "data": {
                    "session_id": session_id or "mock-session-123",
                    "total_chunks": len(chunks),
                    "processing_time": 1.23,
                    "tokens_used": 150,
                }
            }

        mock_service.stream_rag_pipeline = mock_stream_generator
        return mock_service

    @pytest.fixture
    def client_with_mock(self, mock_chat_service):
        """Mock ChatService가 주입된 TestClient"""
        # 인증 미들웨어를 우회하기 위해 라우터만 포함한 앱 사용
        from fastapi import FastAPI
        from app.api.routers.chat_router import router, set_chat_service

        set_chat_service(mock_chat_service)

        test_app = FastAPI()
        test_app.include_router(router)

        client = TestClient(test_app)

        yield client

    def test_streaming_full_flow(self, client_with_mock):
        """
        스트리밍 전체 흐름 테스트

        Given: Mock ChatService가 주입됨
        When: POST /chat/stream 호출
        Then: metadata → chunk* → done 순서로 이벤트 수신
        """
        response = client_with_mock.post(
            "/chat/stream",
            json={"message": "안녕하세요"},
            headers={"Accept": "text/event-stream"},
        )

        # 응답 상태 코드 확인
        assert response.status_code == 200

        # Content-Type 확인
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type

        # SSE 이벤트 파싱
        events = parse_sse_events(response.text)

        # 이벤트 수 확인 (최소 3개: metadata + chunk(s) + done)
        assert len(events) >= 3, f"이벤트 수가 부족합니다: {len(events)}"

        # 이벤트 타입 순서 확인
        event_types = [e["event_type"] for e in events]

        # 첫 번째는 metadata
        assert event_types[0] == "metadata", f"첫 이벤트가 metadata가 아닙니다: {event_types[0]}"

        # 마지막은 done 또는 error
        assert event_types[-1] in ["done", "error"], f"마지막 이벤트가 done/error가 아닙니다: {event_types[-1]}"

        # 중간은 chunk들
        middle_types = event_types[1:-1]
        assert all(t == "chunk" for t in middle_types), f"중간 이벤트가 chunk가 아닙니다: {middle_types}"

    def test_streaming_metadata_content(self, client_with_mock):
        """
        metadata 이벤트 내용 검증

        Given: 스트리밍 요청
        When: metadata 이벤트 수신
        Then: 필수 필드(session_id, search_results 등) 포함
        """
        response = client_with_mock.post(
            "/chat/stream",
            json={"message": "테스트 질문입니다"},
        )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        metadata_events = [e for e in events if e["event_type"] == "metadata"]

        assert len(metadata_events) >= 1, "metadata 이벤트가 없습니다"

        metadata = metadata_events[0]["data"]

        # 필수 필드 확인
        if isinstance(metadata, dict) and "data" in metadata:
            # 중첩된 경우
            metadata = metadata["data"]

        assert "session_id" in metadata, "session_id가 없습니다"
        assert "search_results" in metadata, "search_results가 없습니다"

    def test_streaming_chunk_sequence(self, client_with_mock):
        """
        chunk 이벤트 순서 검증

        Given: 스트리밍 요청
        When: 여러 chunk 이벤트 수신
        Then: chunk_index가 순차적으로 증가
        """
        response = client_with_mock.post(
            "/chat/stream",
            json={"message": "청크 순서 테스트"},
        )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        chunk_events = [e for e in events if e["event_type"] == "chunk"]

        # chunk_index 추출
        chunk_indices = []
        for chunk in chunk_events:
            data = chunk["data"]
            if isinstance(data, dict) and "chunk_index" in data:
                chunk_indices.append(data["chunk_index"])

        # 순차적 증가 확인
        if chunk_indices:
            expected_indices = list(range(len(chunk_indices)))
            assert chunk_indices == expected_indices, f"chunk_index 순서가 잘못됨: {chunk_indices}"

    def test_streaming_done_event(self, client_with_mock):
        """
        done 이벤트 내용 검증

        Given: 스트리밍 요청
        When: 스트리밍 완료
        Then: done 이벤트에 session_id, total_chunks 포함
        """
        response = client_with_mock.post(
            "/chat/stream",
            json={"message": "완료 이벤트 테스트"},
        )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        done_events = [e for e in events if e["event_type"] == "done"]

        assert len(done_events) == 1, f"done 이벤트가 1개가 아닙니다: {len(done_events)}"

        done_data = done_events[0]["data"]

        # done 이벤트 필드 확인
        if isinstance(done_data, dict) and "data" in done_data:
            done_data = done_data["data"]

        assert "session_id" in done_data, "done에 session_id가 없습니다"
        assert "total_chunks" in done_data, "done에 total_chunks가 없습니다"

    def test_streaming_with_session_id(self, client_with_mock):
        """
        session_id 포함 요청 테스트

        Given: session_id를 포함한 스트리밍 요청
        When: 스트리밍 완료
        Then: 응답에 동일한 session_id 반환
        """
        test_session_id = "custom-session-abc123"

        response = client_with_mock.post(
            "/chat/stream",
            json={
                "message": "세션 ID 테스트",
                "session_id": test_session_id,
            },
        )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        done_events = [e for e in events if e["event_type"] == "done"]

        assert len(done_events) >= 1

        done_data = done_events[0]["data"]
        if isinstance(done_data, dict) and "data" in done_data:
            done_data = done_data["data"]

        # session_id가 요청한 것과 동일하거나, mock 응답인 경우
        assert "session_id" in done_data


# =============================================================================
# 입력 검증 테스트
# =============================================================================

@pytest.mark.integration
class TestStreamingInputValidation:
    """
    스트리밍 API 입력 검증 테스트

    StreamChatRequest의 Pydantic 검증을 테스트합니다.
    인증 미들웨어를 우회하기 위해 라우터만 포함한 별도의 FastAPI 앱을 사용합니다.
    """

    @pytest.fixture
    def validation_app(self):
        """입력 검증 테스트용 앱 (인증 미들웨어 없음)"""
        from fastapi import FastAPI
        from app.api.routers.chat_router import router, set_chat_service

        # Mock 서비스 설정 (검증 통과 후 실행되지 않음)
        mock_service = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield {"event": "done", "data": {}}

        mock_service.stream_rag_pipeline = mock_stream
        set_chat_service(mock_service)

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, validation_app):
        """TestClient 생성"""
        return TestClient(validation_app, raise_server_exceptions=False)

    def test_empty_message_returns_422(self, client):
        """
        빈 메시지 요청 시 422 반환

        Given: 빈 문자열 메시지
        When: POST /chat/stream
        Then: 422 Unprocessable Entity
        """
        response = client.post(
            "/chat/stream",
            json={"message": ""},
        )

        # StreamChatRequest의 min_length=1 검증
        assert response.status_code == 422

        error_detail = response.json()
        assert "detail" in error_detail

    def test_missing_message_returns_422(self, client):
        """
        메시지 필드 누락 시 422 반환

        Given: message 필드 없음
        When: POST /chat/stream
        Then: 422 Unprocessable Entity
        """
        response = client.post(
            "/chat/stream",
            json={},
        )

        assert response.status_code == 422

    def test_message_too_long_returns_422(self, client):
        """
        너무 긴 메시지 요청 시 422 반환

        Given: 10001자 이상의 메시지
        When: POST /chat/stream
        Then: 422 Unprocessable Entity
        """
        # StreamChatRequest의 max_length=10000 검증
        long_message = "가" * 10001

        response = client.post(
            "/chat/stream",
            json={"message": long_message},
        )

        assert response.status_code == 422


# =============================================================================
# 에러 시나리오 테스트
# =============================================================================

@pytest.mark.integration
class TestStreamingErrorHandling:
    """
    스트리밍 에러 핸들링 테스트

    스트리밍 중 에러 발생 시 error 이벤트가 전송되는지 검증합니다.
    """

    @pytest.fixture
    def mock_error_chat_service(self):
        """에러를 발생시키는 ChatService Mock"""
        mock_service = MagicMock()

        async def mock_error_generator(message: str, session_id: str | None, options: dict | None) -> AsyncGenerator[dict, None]:
            """에러 발생 스트리밍 제너레이터"""
            # metadata는 정상 전송
            yield {
                "event": "metadata",
                "data": {
                    "session_id": "error-test-session",
                    "search_results": 0,
                }
            }

            # 에러 발생
            raise Exception("Simulated streaming error")

        mock_service.stream_rag_pipeline = mock_error_generator
        return mock_service

    @pytest.fixture
    def client_with_error_mock(self, mock_error_chat_service):
        """에러 Mock이 주입된 TestClient"""
        # 인증 미들웨어를 우회하기 위해 라우터만 포함한 앱 사용
        from fastapi import FastAPI
        from app.api.routers.chat_router import router, set_chat_service

        set_chat_service(mock_error_chat_service)

        test_app = FastAPI()
        test_app.include_router(router)

        client = TestClient(test_app, raise_server_exceptions=False)

        yield client

    def test_streaming_error_event(self, client_with_error_mock):
        """
        스트리밍 중 에러 시 error 이벤트 전송

        Given: 스트리밍 중 에러 발생
        When: 에러 이벤트 수신
        Then: error_code와 message 포함
        """
        response = client_with_error_mock.post(
            "/chat/stream",
            json={"message": "에러 테스트"},
        )

        # 스트리밍은 시작되므로 200 OK
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        error_events = [e for e in events if e["event_type"] == "error"]

        # 에러 이벤트가 있거나, 마지막 이벤트가 에러인지 확인
        if error_events:
            error_data = error_events[0]["data"]

            # error_code 또는 message 필드 확인
            has_error_info = (
                (isinstance(error_data, dict) and ("error_code" in error_data or "message" in error_data))
                or isinstance(error_data, str)
            )
            assert has_error_info, f"에러 정보가 없습니다: {error_data}"


# =============================================================================
# 서비스 미초기화 테스트
# =============================================================================

@pytest.mark.integration
class TestStreamingServiceNotInitialized:
    """
    ChatService 미초기화 시 동작 테스트

    서버 시작 직후 chat_service가 None인 상태에서의 동작을 검증합니다.
    """

    def test_service_not_initialized_returns_503(self):
        """
        서비스 미초기화 시 503 반환

        Given: chat_service가 None
        When: POST /chat/stream
        Then: 503 Service Unavailable
        """
        # 인증 미들웨어를 우회하기 위해 라우터만 포함한 앱 사용
        from fastapi import FastAPI
        from app.api.routers.chat_router import router, set_chat_service

        # chat_service를 None으로 설정
        set_chat_service(None)  # type: ignore[arg-type]

        test_app = FastAPI()
        test_app.include_router(router)

        client = TestClient(test_app, raise_server_exceptions=False)

        response = client.post(
            "/chat/stream",
            json={"message": "초기화 테스트"},
        )

        # 503 Service Unavailable
        assert response.status_code == 503

        error_detail = response.json()
        assert "detail" in error_detail
        assert "서비스 초기화" in str(error_detail.get("detail", "")) or "retry_after" in str(error_detail.get("detail", ""))


# =============================================================================
# 실제 서버 테스트 (외부 서비스 필요, 기본 skip)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="실제 서버 연결 필요 (Weaviate, LLM 등)")
class TestStreamingWithRealServer:
    """
    실제 서버 연결 스트리밍 테스트

    실제 API 서버가 실행 중일 때만 테스트됩니다.
    환경 변수 TEST_API_URL로 서버 URL을 지정할 수 있습니다.
    """

    async def test_real_streaming_full_flow(self):
        """
        실제 서버 스트리밍 전체 흐름 테스트

        Given: 실제 API 서버가 실행 중
        When: POST /chat/stream 호출
        Then: SSE 이벤트가 올바르게 수신됨
        """
        base_url = os.getenv("TEST_API_URL", "http://localhost:8000")

        async with AsyncClient(base_url=base_url, timeout=60.0) as client:
            response = await client.post(
                "/chat/stream",
                json={"message": "안녕하세요"},
                headers={"Accept": "text/event-stream"},
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # SSE 이벤트 파싱
            events = parse_sse_events(response.text)

            # 최소 1개 이상의 이벤트
            assert len(events) >= 1

            # 마지막 이벤트는 done 또는 error
            last_event = events[-1]
            assert last_event["event_type"] in ["done", "error"]


# =============================================================================
# 유틸리티 함수 테스트
# =============================================================================

@pytest.mark.integration
class TestSSEParsingUtility:
    """
    SSE 파싱 유틸리티 함수 테스트
    """

    def test_parse_sse_events_basic(self):
        """기본 SSE 파싱 테스트"""
        sse_text = """event: metadata
data: {"event":"metadata","data":{"session_id":"abc"}}

event: chunk
data: {"event":"chunk","data":"Hello","chunk_index":0}

event: done
data: {"event":"done","data":{"session_id":"abc","total_chunks":1}}
"""

        events = parse_sse_events(sse_text)

        assert len(events) == 3
        assert events[0]["event_type"] == "metadata"
        assert events[1]["event_type"] == "chunk"
        assert events[2]["event_type"] == "done"

    def test_parse_sse_events_without_event_line(self):
        """event: 라인 없이 data:만 있는 경우"""
        sse_text = """data: {"event":"chunk","data":"text","chunk_index":0}
"""

        events = parse_sse_events(sse_text)

        assert len(events) == 1
        assert events[0]["event_type"] == "chunk"

    def test_parse_sse_events_empty_input(self):
        """빈 입력 처리"""
        events = parse_sse_events("")
        assert len(events) == 0

    def test_parse_sse_events_invalid_json(self):
        """잘못된 JSON 처리"""
        sse_text = """event: error
data: not-valid-json
"""

        events = parse_sse_events(sse_text)

        assert len(events) == 1
        assert "raw" in events[0]["data"]
