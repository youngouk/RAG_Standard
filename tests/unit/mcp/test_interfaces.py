"""MCP 인터페이스 테스트"""

from dataclasses import is_dataclass


def test_mcp_tool_result_is_dataclass():
    """MCPToolResult가 dataclass인지 확인"""
    from app.modules.core.mcp.interfaces import MCPToolResult

    assert is_dataclass(MCPToolResult)


def test_mcp_tool_result_fields():
    """MCPToolResult 필드 확인"""
    from app.modules.core.mcp.interfaces import MCPToolResult

    result = MCPToolResult(
        success=True,
        data={"key": "value"},
        error=None,
        tool_name="test_tool",
        execution_time=0.5,
    )

    assert result.success is True
    assert result.data == {"key": "value"}
    assert result.error is None
    assert result.tool_name == "test_tool"
    assert result.execution_time == 0.5


def test_mcp_tool_result_default_values():
    """MCPToolResult 기본값 확인"""
    from app.modules.core.mcp.interfaces import MCPToolResult

    result = MCPToolResult(
        success=False,
        data=None,
    )

    assert result.success is False
    assert result.data is None
    assert result.error is None
    assert result.tool_name == ""
    assert result.execution_time == 0.0


def test_mcp_tool_config_fields():
    """MCPToolConfig 필드 확인"""
    from app.modules.core.mcp.interfaces import MCPToolConfig

    config = MCPToolConfig(
        name="search_weaviate",
        description="Weaviate 검색",
        enabled=True,
        timeout=30.0,
    )

    assert config.name == "search_weaviate"
    assert config.description == "Weaviate 검색"
    assert config.enabled is True
    assert config.timeout == 30.0


def test_mcp_tool_config_default_values():
    """MCPToolConfig 기본값 확인"""
    from app.modules.core.mcp.interfaces import MCPToolConfig

    config = MCPToolConfig(
        name="test_tool",
        description="테스트 도구",
    )

    assert config.enabled is True  # 기본값 True
    assert config.timeout == 30.0  # 기본값 30초
    assert config.retry_count == 1  # 기본값 1회


def test_mcp_server_config_fields():
    """MCPServerConfig 필드 확인"""
    from app.modules.core.mcp.interfaces import MCPServerConfig

    config = MCPServerConfig(
        enabled=True,
        server_name="test-server",
        default_timeout=60.0,
        max_concurrent_tools=5,
    )

    assert config.enabled is True
    assert config.server_name == "test-server"
    assert config.default_timeout == 60.0
    assert config.max_concurrent_tools == 5


def test_mcp_server_config_default_values():
    """MCPServerConfig 기본값 확인"""
    from app.modules.core.mcp.interfaces import MCPServerConfig

    config = MCPServerConfig()

    assert config.enabled is True
    # 범용화: 도메인 특화 이름에서 일반 이름으로 변경됨
    assert config.server_name == "blank-rag-system"
    assert config.default_timeout == 30.0
    assert config.max_concurrent_tools == 3


