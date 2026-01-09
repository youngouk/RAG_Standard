"""
MCP 인터페이스 및 타입 정의

기존 IEmbedder, IReranker 패턴을 따름.
FastMCP와 통합하면서도 팩토리 패턴 호환성 유지.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPToolResult:
    """
    MCP 도구 실행 결과

    Attributes:
        success: 실행 성공 여부
        data: 실행 결과 데이터
        error: 에러 메시지 (실패 시)
        tool_name: 실행된 도구 이름
        execution_time: 실행 시간 (초)
        metadata: 추가 메타데이터
    """

    success: bool
    data: Any
    error: str | None = None
    tool_name: str = ""
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolConfig:
    """
    MCP 도구 설정

    YAML 설정에서 로드되어 도구별 동작을 제어합니다.

    Attributes:
        name: 도구 이름 (예: "search_weaviate")
        description: 도구 설명 (LLM이 도구 선택 시 참고)
        enabled: 활성화 여부 (YAML에서 On/Off)
        timeout: 실행 타임아웃 (초)
        retry_count: 재시도 횟수
        parameters: 도구별 추가 파라미터
    """

    name: str
    description: str
    enabled: bool = True
    timeout: float = 30.0
    retry_count: int = 1
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    """
    MCP 서버 전체 설정

    YAML의 mcp 섹션에서 로드됩니다.

    Attributes:
        enabled: MCP 기능 전체 활성화 여부
        server_name: MCP 서버 이름
        default_timeout: 기본 타임아웃 (초)
        max_concurrent_tools: 동시 실행 가능한 도구 수
        tools: 등록된 도구 설정 (도구명 → MCPToolConfig)
    """

    enabled: bool = True
    server_name: str = "blank-rag-system"
    default_timeout: float = 30.0
    max_concurrent_tools: int = 3
    tools: dict[str, MCPToolConfig] = field(default_factory=dict)


# 도구 함수 타입 힌트
# async def tool_func(arguments: dict, config: dict) -> Any
MCPToolFunction = Callable[..., Coroutine[Any, Any, Any]]

