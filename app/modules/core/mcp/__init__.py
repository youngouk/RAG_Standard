"""
MCP (Model Context Protocol) 모듈

FastMCP 기반 MCP 서버 및 도구 관리.
기존 EmbedderFactory, RerankerFactory와 동일한 팩토리 패턴 적용.

사용 예시:
    from app.modules.core.mcp import MCPToolFactory, MCPServer

    # 설정 기반 MCP 서버 생성
    mcp = MCPToolFactory.create(config)

    # 도구 실행
    result = await mcp.execute_tool("search_weaviate", {"query": "검색어"})
"""

from .factory import SUPPORTED_TOOLS, MCPToolFactory
from .interfaces import (
    MCPServerConfig,
    MCPToolConfig,
    MCPToolFunction,
    MCPToolResult,
)
from .server import MCPServer

__all__ = [
    # interfaces
    "MCPToolResult",
    "MCPToolConfig",
    "MCPServerConfig",
    "MCPToolFunction",
    # factory
    "MCPToolFactory",
    "SUPPORTED_TOOLS",
    # server
    "MCPServer",
]

