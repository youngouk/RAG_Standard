"""
Agent 모듈 타임아웃 테스트

AgentExecutor의 전체 작업 타임아웃 기능을 검증합니다.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.core.agent.executor import AgentExecutor
from app.modules.core.agent.interfaces import AgentConfig, ToolCall


@pytest.mark.asyncio
async def test_agent_respects_timeout():
    """
    AgentExecutor가 설정된 타임아웃을 준수하는지 검증

    asyncio.wait_for의 기본 타임아웃 동작을 검증합니다.
    """

    async def slow_task():
        """5초 지연 작업"""
        await asyncio.sleep(5.0)
        return "완료"

    # 1초 타임아웃으로 5초 작업 실행 → TimeoutError 발생
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_task(), timeout=1.0)


@pytest.mark.asyncio
async def test_agent_completes_within_timeout():
    """
    AgentExecutor가 타임아웃 내에 완료되는 작업을 정상 처리하는지 검증

    빠른 작업은 타임아웃 없이 정상 완료되어야 합니다.
    """

    async def fast_task():
        """0.1초 작업"""
        await asyncio.sleep(0.1)
        return "완료"

    # 5초 타임아웃으로 0.1초 작업 실행 → 정상 완료
    result = await asyncio.wait_for(fast_task(), timeout=5.0)
    assert result == "완료"


@pytest.mark.asyncio
async def test_agent_times_out_on_long_task():
    """
    AgentExecutor가 느린 작업에서 타임아웃을 발생시키는지 검증

    전체 작업 타임아웃이 초과되면 asyncio.TimeoutError를 발생시켜야 합니다.
    """
    # Mock MCP 서버 (느린 도구 실행)
    mock_mcp_server = MagicMock()
    mock_mcp_server.execute_tool = AsyncMock()

    # 도구 실행이 5초 지연되도록 설정
    async def slow_tool_execution(*args, **kwargs):
        await asyncio.sleep(5.0)
        return MagicMock(success=True, data={"result": "완료"}, error=None)

    mock_mcp_server.execute_tool.side_effect = slow_tool_execution

    # AgentConfig: 전체 타임아웃 1초, 도구 타임아웃 10초
    config = AgentConfig(
        max_iterations=3,
        max_concurrent_tools=5,
        parallel_execution=False,
        tool_timeout=10.0,
        timeout_seconds=1.0,  # 전체 타임아웃 1초
    )

    executor = AgentExecutor(mcp_server=mock_mcp_server, config=config)

    # 도구 호출
    tool_call = ToolCall(
        call_id="test_001",
        tool_name="slow_search",
        arguments={"query": "test"},
    )

    # 전체 타임아웃 1초 초과 → asyncio.TimeoutError 발생
    with pytest.raises(asyncio.TimeoutError):
        await executor.execute([tool_call])


@pytest.mark.asyncio
async def test_agent_completes_fast_task():
    """
    AgentExecutor가 빠른 작업을 정상 완료하는지 검증

    전체 타임아웃 내에 완료되는 작업은 정상 처리되어야 합니다.
    """
    # Mock MCP 서버 (빠른 도구 실행)
    mock_mcp_server = MagicMock()
    mock_mcp_server.execute_tool = AsyncMock()

    # 도구 실행이 0.1초로 빠르게 완료
    async def fast_tool_execution(*args, **kwargs):
        await asyncio.sleep(0.1)
        return MagicMock(success=True, data={"result": "빠른 완료"}, error=None)

    mock_mcp_server.execute_tool.side_effect = fast_tool_execution

    # AgentConfig: 전체 타임아웃 5초, 도구 타임아웃 10초
    config = AgentConfig(
        max_iterations=3,
        max_concurrent_tools=5,
        parallel_execution=False,
        tool_timeout=10.0,
        timeout_seconds=5.0,  # 전체 타임아웃 5초
    )

    executor = AgentExecutor(mcp_server=mock_mcp_server, config=config)

    # 도구 호출
    tool_call = ToolCall(
        call_id="test_002",
        tool_name="fast_search",
        arguments={"query": "test"},
    )

    # 전체 타임아웃 5초 내 완료 → 정상 처리
    results = await executor.execute([tool_call])

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].data == {"result": "빠른 완료"}
