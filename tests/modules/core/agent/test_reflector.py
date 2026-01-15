"""
AgentReflector 테스트

Self-Reflection 기능의 핵심 로직 검증:
- 초기화 및 의존성 검증
- reflect() 메서드 동작 검증
"""
import pytest
from unittest.mock import MagicMock

from app.modules.core.agent.reflector import AgentReflector
from app.modules.core.agent.interfaces import AgentConfig


class TestAgentReflectorInit:
    """AgentReflector 초기화 테스트"""

    def test_reflector_init_success(self):
        """정상 초기화 테스트"""
        # Given: Mock LLM 클라이언트와 설정
        llm_client = MagicMock()
        config = AgentConfig()

        # When: AgentReflector 초기화
        reflector = AgentReflector(llm_client=llm_client, config=config)

        # Then: 의존성이 올바르게 저장됨
        assert reflector._llm_client is llm_client
        assert reflector._config is config

    def test_reflector_init_without_llm_raises(self):
        """llm_client 없이 초기화 시 ValueError 발생"""
        # Given: config만 있고 llm_client가 None
        config = AgentConfig()

        # When/Then: ValueError 발생
        with pytest.raises(ValueError, match="llm_client는 필수"):
            AgentReflector(llm_client=None, config=config)

    def test_reflector_init_without_config_raises(self):
        """config 없이 초기화 시 ValueError 발생"""
        # Given: llm_client만 있고 config가 None
        llm_client = MagicMock()

        # When/Then: ValueError 발생
        with pytest.raises(ValueError, match="config는 필수"):
            AgentReflector(llm_client=llm_client, config=None)
