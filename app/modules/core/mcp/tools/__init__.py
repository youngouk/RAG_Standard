"""
MCP 도구 모듈

각 도구는 독립적인 파일로 구현됩니다.
FastMCP의 @mcp.tool() 데코레이터와 호환됩니다.

도구 함수 시그니처:
    async def tool_function(arguments: dict, global_config: dict) -> Any

예시:
    from app.modules.core.mcp.tools.weaviate import search_weaviate

    result = await search_weaviate(
        {"query": "검색어", "top_k": 5},
        global_config
    )

    from app.modules.core.mcp.tools.graph_tools import search_graph, get_neighbors

    result = await search_graph(
        query="A 업체",
        graph_store=graph_store,
    )
"""

from . import weaviate
from .graph_tools import get_neighbors, search_graph

__all__ = ["weaviate", "search_graph", "get_neighbors"]

