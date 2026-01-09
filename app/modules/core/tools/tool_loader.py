"""
Tool 정의 로더
YAML 파일에서 Tool 정의를 로드하고 관리
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ....lib.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    """Tool 정의 데이터 클래스"""

    name: str
    display_name: str
    category: str
    description: str
    parameters: dict[str, Any]
    execution: dict[str, Any]
    response_schema: dict[str, Any] | None = None
    examples: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None

    def to_llm_function_schema(self) -> dict[str, Any]:
        """
        LLM Function Calling용 스키마로 변환
        OpenAI, Gemini, Claude 호환 형식
        """
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    def is_external_api(self) -> bool:
        """외부 API 호출 Tool인지 확인"""
        return self.execution.get("type") == "external_api"

    def is_internal_function(self) -> bool:
        """내부 함수 실행 Tool인지 확인"""
        return self.execution.get("type") == "internal_function"


class ToolLoader:
    """
    Tool 정의 로더
    YAML 파일에서 Tool 정의를 로드하고 관리
    """

    def __init__(self, config_path: Path | None = None):
        """
        Args:
            config_path: Tool 정의 YAML 파일 경로
                        None이면 기본 경로 사용
        """
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent.parent.parent / "config" / "tool_definitions.yaml"
            )
        self.config_path = config_path
        self.tools: dict[str, ToolDefinition] = {}
        self.categories: dict[str, dict[str, Any]] = {}
        self.settings: dict[str, Any] = {}
        self._loaded = False
        logger.info(f"ToolLoader 초기화: {self.config_path}")

    def load(self) -> None:
        """Tool 정의 YAML 파일 로드"""
        if self._loaded:
            logger.debug("Tool 정의가 이미 로드됨")
            return
        if not self.config_path.exists():
            logger.error(f"Tool 정의 파일을 찾을 수 없음: {self.config_path}")
            raise FileNotFoundError(f"Tool definitions file not found: {self.config_path}")
        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self.categories = {cat["id"]: cat for cat in config.get("categories", [])}
            logger.info(f"로드된 카테고리: {len(self.categories)}개")
            for tool_data in config.get("tools", []):
                tool_def = ToolDefinition(
                    name=tool_data["name"],
                    display_name=tool_data.get("display_name", tool_data["name"]),
                    category=tool_data.get("category", "default"),
                    description=tool_data["description"],
                    parameters=tool_data["parameters"],
                    execution=tool_data["execution"],
                    response_schema=tool_data.get("response_schema"),
                    examples=tool_data.get("examples"),
                    metadata=tool_data.get("metadata", {}),
                )

                # 환경 변수 치환 시도 (에러 발생 시 Tool 건너뛰기)
                try:
                    self._substitute_env_variables(tool_def)
                    self.tools[tool_def.name] = tool_def
                    logger.debug(f"Tool 로드: {tool_def.name} ({tool_def.category})")
                except ValueError as e:
                    # 필수 환경 변수가 없으면 Tool을 건너뛰고 비활성화
                    logger.warning(f"Tool 건너뛰기 (환경 변수 누락): {tool_def.name} - {e}")
                    if tool_def.metadata is None:
                        tool_def.metadata = {}
                    tool_def.metadata["status"] = "disabled"
                    tool_def.metadata["disabled_reason"] = str(e)
                    # Tool을 로드하되 비활성화 상태로 추가
                    self.tools[tool_def.name] = tool_def
                    logger.info(f"Tool 비활성화됨: {tool_def.name} (환경 변수 없음)")
            self.settings = config.get("settings", {})
            self._loaded = True
            logger.info(f"Tool 정의 로드 완료: {len(self.tools)}개")
        except yaml.YAMLError as e:
            logger.error(f"YAML 파싱 오류: {e}")
            raise ValueError(f"Failed to parse tool definitions YAML: {e}") from e
        except Exception as e:
            logger.error(f"Tool 정의 로드 실패: {e}")
            raise

    def _substitute_env_variables(self, tool_def: ToolDefinition) -> None:
        """
        Tool 정의 내 환경변수 치환
        ${ENV_VAR} 형식을 실제 환경변수 값으로 치환
        """
        execution = tool_def.execution
        if "base_url_env" in execution:
            env_key = execution["base_url_env"]
            base_url = os.getenv(env_key)
            if not base_url:
                logger.warning(f"환경변수 {env_key}가 설정되지 않음 (Tool: {tool_def.name})")
            execution["base_url"] = base_url
        if "headers" in execution:
            for key, value in execution["headers"].items():
                if isinstance(value, str) and "${" in value:
                    import re

                    match = re.search("\\$\\{(\\w+)\\}", value)
                    if match:
                        env_key = match.group(1)
                        env_value = os.getenv(env_key)
                        if not env_value:
                            if "authorization" in key.lower() or "token" in key.lower():
                                logger.error(
                                    f"필수 환경 변수 누락: {env_key} (Tool: {tool_def.name})"
                                )
                                raise ValueError(
                                    f"Required environment variable {env_key} not set for tool {tool_def.name}"
                                )
                            else:
                                logger.warning(
                                    f"환경 변수 {env_key}가 설정되지 않음 (Tool: {tool_def.name})"
                                )
                                env_value = ""
                        execution["headers"][key] = value.replace(f"${{{env_key}}}", env_value)

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """
        Tool 이름으로 정의 조회

        Args:
            tool_name: Tool 이름

        Returns:
            ToolDefinition 또는 None
        """
        if not self._loaded:
            self.load()
        return self.tools.get(tool_name)

    def get_all_tools(self) -> list[ToolDefinition]:
        """
        모든 Tool 정의 조회

        Returns:
            Tool 정의 리스트
        """
        if not self._loaded:
            self.load()
        return list(self.tools.values())

    def get_tools_by_category(self, category: str) -> list[ToolDefinition]:
        """
        카테고리별 Tool 정의 조회

        Args:
            category: 카테고리 ID

        Returns:
            해당 카테고리의 Tool 리스트
        """
        if not self._loaded:
            self.load()
        return [tool for tool in self.tools.values() if tool.category == category]

    def get_llm_function_schemas(self) -> list[dict[str, Any]]:
        """
        LLM Function Calling용 스키마 목록 반환
        OpenAI, Gemini, Claude 호환 형식
        활성화된 Tool만 반환 (환경 변수가 없는 Tool은 제외)

        Returns:
            LLM Function 스키마 리스트
        """
        if not self._loaded:
            self.load()
        return [
            tool.to_llm_function_schema()
            for tool in self.tools.values()
            if tool.metadata
            and tool.metadata.get("status") == "active"
            and tool.metadata.get("disabled_reason") is None
        ]

    def validate_tool_parameters(
        self, tool_name: str, parameters: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Tool 파라미터 검증

        Args:
            tool_name: Tool 이름
            parameters: 검증할 파라미터

        Returns:
            (검증 성공 여부, 오류 메시지)
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return (False, f"Unknown tool: {tool_name}")
        param_schema = tool.parameters
        required_fields = param_schema.get("required", [])
        for field in required_fields:
            if field not in parameters:
                return (False, f"Missing required parameter: {field}")
        return (True, None)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        글로벌 설정 조회

        Args:
            key: 설정 키 (점 표기법 지원, 예: 'logging.log_requests')
            default: 기본값

        Returns:
            설정 값
        """
        if not self._loaded:
            self.load()
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def reload(self) -> None:
        """Tool 정의 재로드"""
        self._loaded = False
        self.tools.clear()
        self.categories.clear()
        self.settings.clear()
        self.load()
        logger.info("Tool 정의 재로드 완료")


_tool_loader: ToolLoader | None = None


def get_tool_loader() -> ToolLoader:
    """
    ToolLoader 싱글톤 인스턴스 반환

    Returns:
        ToolLoader 인스턴스
    """
    global _tool_loader
    if _tool_loader is None:
        _tool_loader = ToolLoader()
        _tool_loader.load()
    return _tool_loader
