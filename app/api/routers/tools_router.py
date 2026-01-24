"""
Tools Router - Tool Use API 엔드포인트
LLM Tool Use (Function Calling) 기능을 위한 API 라우터

## 제공 엔드포인트
- GET /api/tools - 사용 가능한 Tool 목록 조회
- GET /api/tools/{tool_name} - 특정 Tool 상세 정보 조회
- POST /api/tools/{tool_name}/execute - Tool 실행
"""

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...lib.auth import get_api_key
from ...lib.logger import get_logger
from ...modules.core.tools import ToolExecutionResult, ToolExecutor

logger = get_logger(__name__)
router = APIRouter()
tool_executor: ToolExecutor | None = None


def set_tool_executor(executor: ToolExecutor) -> None:
    """ToolExecutor 의존성 주입"""
    global tool_executor
    tool_executor = executor
    logger.info("ToolExecutor 주입 완료")


class ToolExecuteRequest(BaseModel):
    """Tool 실행 요청"""

    parameters: dict[str, Any] = Field(..., description="Tool 실행 파라미터")
    context: dict[str, Any] | None = Field(None, description="요청 컨텍스트 정보 (선택사항)")


class ToolExecuteResponse(BaseModel):
    """Tool 실행 응답"""

    success: bool = Field(..., description="실행 성공 여부")
    tool_name: str = Field(..., description="실행된 Tool 이름")
    data: dict[str, Any] | None = Field(None, description="실행 결과 데이터")
    error: dict[str, str] | None = Field(None, description="에러 정보")
    execution_time_ms: float | None = Field(None, description="실행 시간 (밀리초)")
    metadata: dict[str, Any] | None = Field(None, description="메타데이터")
    request_id: str = Field(..., description="요청 ID")


class ToolInfoResponse(BaseModel):
    """Tool 정보 응답"""

    name: str = Field(..., description="Tool 이름")
    display_name: str = Field(..., description="Tool 표시 이름")
    category: str = Field(..., description="Tool 카테고리")
    description: str = Field(..., description="Tool 설명")
    parameters: dict[str, Any] = Field(..., description="Tool 파라미터 스키마")
    metadata: dict[str, Any] | None = Field(None, description="메타데이터")


class ToolListResponse(BaseModel):
    """Tool 목록 응답"""

    tools: list[dict[str, Any]] = Field(..., description="Tool 목록")
    total_count: int = Field(..., description="전체 Tool 수")


@router.get("/tools", response_model=ToolListResponse)
async def get_tools(category: str | None = None) -> ToolListResponse:
    """
    사용 가능한 Tool 목록 조회

    Args:
        category: 카테고리 필터 (선택사항)

    Returns:
        Tool 목록
    """
    try:
        if not tool_executor:
            raise HTTPException(status_code=500, detail="ToolExecutor가 초기화되지 않았습니다")
        tools = tool_executor.get_available_tools()
        if category:
            tools = [tool for tool in tools if tool.get("category") == category]
        logger.info(f"Tool 목록 조회 완료: {len(tools)}개")
        return ToolListResponse(tools=tools, total_count=len(tools))
    except Exception as e:
        logger.error(f"Tool 목록 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Tool 목록을 가져오는데 실패했습니다. 다시 시도하거나 관리자에게 문의하세요.",
        ) from e


@router.get("/tools/{tool_name}", response_model=ToolInfoResponse)
async def get_tool_info(tool_name: str) -> ToolInfoResponse:
    """
    특정 Tool의 상세 정보 조회

    Args:
        tool_name: Tool 이름

    Returns:
        Tool 상세 정보
    """
    try:
        if not tool_executor:
            raise HTTPException(status_code=500, detail="ToolExecutor가 초기화되지 않았습니다")
        tool_info = tool_executor.get_tool_info(tool_name)
        if not tool_info:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}'을 찾을 수 없습니다")
        logger.info(f"Tool 정보 조회 완료: {tool_name}")
        return ToolInfoResponse(**tool_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tool 정보 조회 실패: {tool_name} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Tool 정보를 가져오는데 실패했습니다. 다시 시도하거나 관리자에게 문의하세요.",
        ) from e


# ✅ H3 보안 패치: Tool 실행은 위험할 수 있으므로 인증 필요
@router.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse, dependencies=[Depends(get_api_key)])
async def execute_tool(tool_name: str, request: ToolExecuteRequest) -> ToolExecuteResponse:
    """
    Tool 실행

    Args:
        tool_name: 실행할 Tool 이름
        request: Tool 실행 요청

    Returns:
        Tool 실행 결과
    """
    request_id = str(uuid4())
    start_time = time.time()
    try:
        if not tool_executor:
            raise HTTPException(status_code=500, detail="ToolExecutor가 초기화되지 않았습니다")
        logger.info(f"Tool 실행 요청: {tool_name} (request_id: {request_id})")
        parameters = request.parameters.copy()
        if request.context:
            parameters["context"] = request.context
        result: ToolExecutionResult = await tool_executor.execute_tool(
            tool_name=tool_name, parameters=parameters
        )
        total_time_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Tool 실행 완료: {tool_name} (성공: {result.success}, 전체 시간: {total_time_ms:.0f}ms)"
        )
        return ToolExecuteResponse(
            success=result.success,
            tool_name=result.tool_name,
            data=result.data,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            metadata=result.metadata,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        total_time_ms = (time.time() - start_time) * 1000
        logger.error(f"Tool 실행 예외 발생: {tool_name} - {str(e)} (request_id: {request_id})")
        return ToolExecuteResponse(
            success=False,
            tool_name=tool_name,
            data=None,
            error={"code": "EXECUTION_EXCEPTION", "message": f"Tool 실행 중 예외 발생: {str(e)}"},
            execution_time_ms=total_time_ms,
            metadata=None,
            request_id=request_id,
        )


@router.get("/tools/health")
async def tools_health_check() -> dict[str, Any]:
    """
    Tool Use 시스템 헬스 체크

    Returns:
        시스템 상태 정보
    """
    try:
        is_initialized = tool_executor is not None
        tools_count = len(tool_executor.get_available_tools()) if is_initialized else 0  # type: ignore[union-attr]
        return {
            "status": "healthy" if is_initialized else "not_initialized",
            "tool_executor_initialized": is_initialized,
            "available_tools_count": tools_count,
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Tool Use 헬스 체크 실패: {str(e)}")
        return {"status": "unhealthy", "error": str(e), "timestamp": time.time()}
