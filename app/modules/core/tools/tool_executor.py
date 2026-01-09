"""
Tool 실행 통합 모듈
내부 Tool(Python 함수)과 외부 Tool(API 호출)을 통합 관리하고 실행
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ....lib.logger import get_logger
from .external_api_caller import APICallResult, ExternalAPICaller
from .tool_loader import ToolDefinition, ToolLoader

logger = get_logger(__name__)


@dataclass
class ToolExecutionResult:
    """Tool 실행 결과"""

    success: bool
    tool_name: str
    data: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    execution_time_ms: float | None = None
    metadata: dict[str, Any] | None = None


class ToolExecutor:
    """
    Tool 실행 통합 관리자
    내부 Tool과 외부 Tool을 통합하여 실행
    """

    def __init__(self, tool_loader: ToolLoader, api_caller: ExternalAPICaller):
        """
        초기화

        Args:
            tool_loader: Tool 정의 로더 (DI)
            api_caller: 외부 API 호출기 (DI)
        """
        self.tool_loader = tool_loader
        self.api_caller = api_caller

        # 내부 Tool 핸들러 등록 (함수명 -> 실제 함수 매핑)
        self.internal_handlers: dict[str, Callable] = {}

        logger.info("ToolExecutor 초기화")

    async def initialize(self):
        """
        비동기 초기화
        ToolLoader와 ExternalAPICaller는 DI Container에서 주입됨
        """
        # global function 호출 제거
        # ToolLoader와 ExternalAPICaller는 생성자에서 DI로 주입됨

        logger.info("ToolExecutor 초기화 완료")

    def register_internal_handler(
        self, handler_name: str, handler_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    ) -> None:
        """
        내부 Tool 핸들러 등록

        Args:
            handler_name: 핸들러 이름 (tool_definitions.yaml의 execution.handler와 매칭)
            handler_func: 실제 실행할 비동기 함수
        """
        self.internal_handlers[handler_name] = handler_func
        logger.info(f"내부 Tool 핸들러 등록: {handler_name}")

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> ToolExecutionResult:
        """
        Tool 실행 (통합 인터페이스)

        Args:
            tool_name: 실행할 Tool 이름
            parameters: Tool 파라미터

        Returns:
            Tool 실행 결과
        """
        import time

        start_time = time.time()

        try:
            # Tool Loader 초기화 확인
            if not self.tool_loader:
                logger.error("ToolLoader가 초기화되지 않음. initialize()를 먼저 호출하세요.")
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error={
                        "code": "NOT_INITIALIZED",
                        "message": "ToolExecutor가 초기화되지 않았습니다",
                    },
                )

            # Tool 정의 조회
            tool_def = self.tool_loader.get_tool(tool_name)
            if not tool_def:
                logger.error(f"Tool을 찾을 수 없음: {tool_name}")
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error={
                        "code": "TOOL_NOT_FOUND",
                        "message": f"Tool '{tool_name}'을 찾을 수 없습니다",
                    },
                )

            # 비활성화된 Tool 확인
            if tool_def.metadata and tool_def.metadata.get("status") == "disabled":
                disabled_reason = tool_def.metadata.get("disabled_reason", "알 수 없는 이유")
                logger.warning(f"비활성화된 Tool 실행 시도: {tool_name} - {disabled_reason}")
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error={
                        "code": "TOOL_DISABLED",
                        "message": f"Tool '{tool_name}'이 비활성화되어 있습니다: {disabled_reason}",
                    },
                )

            # Tool 파라미터 검증
            is_valid, error_msg = self.tool_loader.validate_tool_parameters(tool_name, parameters)
            if not is_valid:
                logger.error(f"Tool 파라미터 검증 실패: {tool_name}, {error_msg}")
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error={
                        "code": "INVALID_PARAMETERS",
                        "message": str(error_msg),  # str 타입 명시적 변환
                    },
                )

            logger.info(f"Tool 실행 시작: {tool_name}")

            # Tool 타입에 따라 실행 라우팅
            if tool_def.is_external_api():
                result = await self._execute_external_tool(tool_def, parameters)
            elif tool_def.is_internal_function():
                result = await self._execute_internal_tool(tool_def, parameters)
            else:
                logger.error(f"알 수 없는 Tool 타입: {tool_def.execution.get('type')}")
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error={
                        "code": "UNKNOWN_TOOL_TYPE",
                        "message": f"알 수 없는 Tool 타입: {tool_def.execution.get('type')}",
                    },
                )

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Tool 실행 완료: {tool_name} "
                f"(성공: {result.success}, 실행 시간: {execution_time_ms:.0f}ms)"
            )

            return ToolExecutionResult(
                success=result.success,
                tool_name=tool_name,
                data=result.data,
                error=result.error,
                execution_time_ms=execution_time_ms,
                metadata={
                    "tool_category": tool_def.category,
                    "execution_type": tool_def.execution.get("type"),
                },
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Tool 실행 중 예외 발생: {tool_name} - {str(e)}")

            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error={"code": "EXECUTION_ERROR", "message": f"Tool 실행 중 오류 발생: {str(e)}"},
                execution_time_ms=execution_time_ms,
            )

    async def _execute_external_tool(
        self, tool_def: ToolDefinition, parameters: dict[str, Any]
    ) -> APICallResult:
        """
        외부 API Tool 실행

        Args:
            tool_def: Tool 정의
            parameters: Tool 파라미터

        Returns:
            API 호출 결과
        """
        logger.debug(f"외부 API Tool 실행: {tool_def.name}")

        # API Caller 초기화 확인
        if not self.api_caller:
            logger.error("ExternalAPICaller가 초기화되지 않음")
            return APICallResult(
                success=False,
                error={
                    "code": "NOT_INITIALIZED",
                    "message": "ExternalAPICaller가 초기화되지 않았습니다",
                },
            )

        # ExternalAPICaller를 통해 HTTP 요청
        result = await self.api_caller.call_api(tool_def, parameters)

        return result

    async def _execute_internal_tool(
        self, tool_def: ToolDefinition, parameters: dict[str, Any]
    ) -> APICallResult:
        """
        내부 함수 Tool 실행

        Args:
            tool_def: Tool 정의
            parameters: Tool 파라미터

        Returns:
            실행 결과 (APICallResult 형식으로 통일)
        """
        import time

        handler_name = tool_def.execution.get("handler")
        if not handler_name:
            logger.error(f"내부 Tool 핸들러가 지정되지 않음: {tool_def.name}")
            return APICallResult(
                success=False,
                error={
                    "code": "MISSING_HANDLER",
                    "message": f"내부 Tool 핸들러가 지정되지 않음: {tool_def.name}",
                },
            )

        # 핸들러 함수 조회
        handler_func = self.internal_handlers.get(handler_name)
        if not handler_func:
            logger.error(f"등록되지 않은 내부 Tool 핸들러: {handler_name}")
            return APICallResult(
                success=False,
                error={
                    "code": "HANDLER_NOT_REGISTERED",
                    "message": f"등록되지 않은 내부 Tool 핸들러: {handler_name}",
                },
            )

        logger.debug(f"내부 Tool 핸들러 실행: {handler_name}")

        start_time = time.time()

        try:
            # 핸들러 함수 실행
            result_data = await handler_func(parameters)

            response_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"내부 Tool 실행 성공: {handler_name} " f"(응답 시간: {response_time_ms:.0f}ms)"
            )

            return APICallResult(success=True, data=result_data, response_time_ms=response_time_ms)

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error(f"내부 Tool 실행 실패: {handler_name} - {str(e)}")

            return APICallResult(
                success=False,
                error={
                    "code": "INTERNAL_HANDLER_ERROR",
                    "message": f"내부 Tool 실행 실패: {str(e)}",
                },
                response_time_ms=response_time_ms,
            )

    def get_available_tools(self) -> list[dict[str, Any]]:
        """
        사용 가능한 모든 Tool 목록 조회 (LLM Function Calling용)

        Returns:
            LLM Function 스키마 리스트
        """
        if not self.tool_loader:
            logger.warning("ToolLoader가 초기화되지 않음")
            return []

        return self.tool_loader.get_llm_function_schemas()

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """
        특정 Tool의 상세 정보 조회

        Args:
            tool_name: Tool 이름

        Returns:
            Tool 정보 딕셔너리 또는 None
        """
        if not self.tool_loader:
            logger.warning("ToolLoader가 초기화되지 않음")
            return None

        tool_def = self.tool_loader.get_tool(tool_name)
        if not tool_def:
            return None

        return {
            "name": tool_def.name,
            "display_name": tool_def.display_name,
            "category": tool_def.category,
            "description": tool_def.description,
            "parameters": tool_def.parameters,
            "metadata": tool_def.metadata,
        }

    async def cleanup(self):
        """
        ToolExecutor 리소스 정리
        - httpx AsyncClient 종료
        - 기타 리소스 정리

        애플리케이션 종료 시 호출 필요
        """
        if self.api_caller:
            await self.api_caller.close()
            logger.info("✅ ToolExecutor cleanup 완료")
