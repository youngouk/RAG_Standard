"""
AgentReflector - Self-Reflection 담당

ReAct 패턴에서 "Reflect" 담당 컴포넌트.
생성된 답변의 품질을 평가하고, 개선이 필요한 부분을 식별합니다.

주요 기능:
- LLM을 사용하여 답변 품질 평가 (0-10점)
- 답변의 문제점 식별 및 개선 제안
- threshold 기반 개선 필요 여부 판단
- 추가 검색이 필요한 키워드 추출

사용 예시:
    reflector = AgentReflector(llm_client, config)
    result = await reflector.reflect(query, answer, context)
    if result.needs_improvement:
        # 개선 로직 실행
"""

from typing import Any

from ....lib.logger import get_logger
from .interfaces import AgentConfig

logger = get_logger(__name__)


class AgentReflector:
    """
    Self-Reflection 담당

    생성된 답변의 품질을 LLM으로 평가하고,
    개선이 필요한 경우 문제점과 제안을 반환합니다.

    Attributes:
        _llm_client: LLM 클라이언트 (generate_text 메서드 필요)
        _config: 에이전트 설정 (reflection_threshold 등)
    """

    def __init__(
        self,
        llm_client: Any,
        config: AgentConfig,
    ):
        """
        AgentReflector 초기화

        Args:
            llm_client: LLM 클라이언트 (generate_text 메서드 필요)
            config: 에이전트 설정

        Raises:
            ValueError: 필수 의존성 누락 시
        """
        if llm_client is None:
            raise ValueError("llm_client는 필수입니다")
        if config is None:
            raise ValueError("config는 필수입니다")

        self._llm_client = llm_client
        self._config = config

        logger.info(
            f"AgentReflector 초기화: "
            f"threshold={config.reflection_threshold}, "
            f"max_iterations={config.max_reflection_iterations}"
        )
