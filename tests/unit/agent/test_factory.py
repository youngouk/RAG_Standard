"""
AgentFactory 테스트

설정 기반 AgentOrchestrator 생성 및 DI Container 통합을 검증하는 단위 테스트.
RerankerFactory, EmbedderFactory와 동일한 팩토리 패턴을 따릅니다.

테스트 케이스:
- 설정 기반 Orchestrator 생성
- MCP 비활성화 시 None 반환
- 설정값 적용 확인
- 기본 설정 조회
- MCP 서버 비활성화 처리
"""

from unittest.mock import MagicMock

import pytest

from app.modules.core.agent.factory import AgentFactory
from app.modules.core.agent.interfaces import AgentConfig
from app.modules.core.agent.orchestrator import AgentOrchestrator


class TestAgentFactory:
    """AgentFactory 단위 테스트"""

    @pytest.fixture
    def mock_config(self) -> dict:
        """Mock 설정 (mcp.yaml 구조 반영)"""
        return {
            "mcp": {
                "enabled": True,
                "agent": {
                    "tool_selection": "llm",
                    "selector_model": "google/gemini-2.5-flash-lite",
                    "max_tool_calls": 5,
                    "fallback_tool": "search_vector_db",
                    "timeout": 60.0,
                    "parallel_execution": True,
                },
            }
        }

    @pytest.fixture
    def mock_config_disabled(self) -> dict:
        """MCP 비활성화 설정"""
        return {
            "mcp": {
                "enabled": False,
            }
        }

    @pytest.fixture
    def mock_config_custom(self) -> dict:
        """커스텀 설정 (기본값과 다른 값)"""
        return {
            "mcp": {
                "enabled": True,
                "agent": {
                    "tool_selection": "rule_based",
                    "selector_model": "gpt-5-turbo",
                    "max_tool_calls": 10,
                    "fallback_tool": "custom_tool",
                    "timeout": 120.0,
                    "parallel_execution": False,
                },
            }
        }

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Mock LLM 클라이언트"""
        client = MagicMock()
        client.generate_text = MagicMock()
        return client

    @pytest.fixture
    def mock_mcp_server(self) -> MagicMock:
        """Mock MCP 서버 (활성화 상태)"""
        server = MagicMock()
        server.get_tool_schemas = MagicMock(return_value=[
            {
                "type": "function",
                "function": {
                    "name": "search_vector_db",
                    "description": "벡터 DB 검색",
                    "parameters": {},
                },
            }
        ])
        server.is_enabled = True
        return server

    @pytest.fixture
    def mock_mcp_server_disabled(self) -> MagicMock:
        """Mock MCP 서버 (비활성화 상태)"""
        server = MagicMock()
        server.is_enabled = False
        return server

    # ========================================
    # 핵심 기능 테스트
    # ========================================

    def test_create_orchestrator(
        self,
        mock_config: dict,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        Orchestrator 생성 테스트

        설정, LLM 클라이언트, MCP 서버를 받아
        AgentOrchestrator 인스턴스를 올바르게 생성하는지 확인합니다.
        """
        # When: AgentFactory.create() 호출
        orchestrator = AgentFactory.create(
            config=mock_config,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: AgentOrchestrator 인스턴스 반환
        assert orchestrator is not None
        assert isinstance(orchestrator, AgentOrchestrator)

    def test_create_disabled_returns_none(
        self,
        mock_config_disabled: dict,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        MCP 비활성화 시 None 반환

        mcp.enabled=False일 때 Orchestrator를 생성하지 않고
        None을 반환하는지 확인합니다.
        """
        # When: MCP 비활성화 설정으로 create() 호출
        result = AgentFactory.create(
            config=mock_config_disabled,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: None 반환
        assert result is None

    def test_create_with_disabled_mcp_server_returns_none(
        self,
        mock_config: dict,
        mock_llm_client: MagicMock,
        mock_mcp_server_disabled: MagicMock,
    ) -> None:
        """
        MCP 서버 비활성화 시 None 반환

        설정은 활성화되어 있지만 MCP 서버의 is_enabled가 False인 경우
        None을 반환하는지 확인합니다.
        """
        # When: MCP 서버가 비활성화된 상태에서 create() 호출
        result = AgentFactory.create(
            config=mock_config,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server_disabled,
        )

        # Then: None 반환
        assert result is None

    def test_create_with_none_mcp_server_returns_none(
        self,
        mock_config: dict,
        mock_llm_client: MagicMock,
    ) -> None:
        """
        MCP 서버가 None인 경우 None 반환

        MCP 서버 인스턴스가 None인 경우 (예: 초기화 실패)
        None을 반환하는지 확인합니다.
        """
        # When: mcp_server=None으로 create() 호출
        result = AgentFactory.create(
            config=mock_config,
            llm_client=mock_llm_client,
            mcp_server=None,
        )

        # Then: None 반환
        assert result is None

    # ========================================
    # 설정값 적용 테스트
    # ========================================

    def test_uses_config_values(
        self,
        mock_config_custom: dict,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        YAML 설정값이 AgentConfig에 올바르게 적용되는지 확인

        커스텀 설정 값들이 생성된 Orchestrator의 config에
        정확히 반영되는지 검증합니다.
        """
        # When: 커스텀 설정으로 create() 호출
        orchestrator = AgentFactory.create(
            config=mock_config_custom,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: 설정값이 올바르게 적용됨
        assert orchestrator is not None
        # Orchestrator 내부의 _config 속성 확인
        config = orchestrator._config
        assert isinstance(config, AgentConfig)
        assert config.tool_selection == "rule_based"
        assert config.selector_model == "gpt-5-turbo"
        assert config.max_iterations == 10
        assert config.fallback_tool == "custom_tool"
        assert config.timeout == 120.0
        assert config.parallel_execution is False

    def test_uses_default_values_when_not_specified(
        self,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        설정값이 없을 때 기본값 사용

        agent 섹션이 비어있거나 일부 설정이 없을 때
        기본값이 적용되는지 확인합니다.
        """
        # Given: agent 섹션이 비어있는 설정
        minimal_config = {
            "mcp": {
                "enabled": True,
                "agent": {},  # 빈 설정
            }
        }

        # When: 최소 설정으로 create() 호출
        orchestrator = AgentFactory.create(
            config=minimal_config,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: 기본값 적용됨
        assert orchestrator is not None
        config = orchestrator._config
        assert config.tool_selection == "llm"  # 기본값
        assert config.max_iterations == 5  # 기본값
        assert config.parallel_execution is True  # 기본값

    # ========================================
    # 유틸리티 메서드 테스트
    # ========================================

    def test_get_default_config(self) -> None:
        """
        기본 설정 조회 테스트

        get_default_config() 메서드가 올바른 기본 설정을
        딕셔너리 형태로 반환하는지 확인합니다.
        """
        # When: 기본 설정 조회
        default_config = AgentFactory.get_default_config()

        # Then: 필수 키들이 존재
        assert "tool_selection" in default_config
        assert "selector_model" in default_config
        assert "max_iterations" in default_config
        assert "fallback_tool" in default_config
        assert "timeout" in default_config
        assert "parallel_execution" in default_config

        # Then: 기본값 검증
        assert default_config["tool_selection"] == "llm"
        assert default_config["max_iterations"] == 5
        assert default_config["parallel_execution"] is True

    def test_create_config(self) -> None:
        """
        AgentConfig 생성 테스트

        create_config() 메서드가 딕셔너리 설정을
        AgentConfig 객체로 변환하는지 확인합니다.
        """
        # Given: 설정 딕셔너리
        config_dict = {
            "mcp": {
                "enabled": True,
                "agent": {
                    "max_tool_calls": 7,
                    "timeout": 90.0,
                },
            }
        }

        # When: create_config() 호출
        agent_config = AgentFactory.create_config(config_dict)

        # Then: AgentConfig 객체 반환
        assert isinstance(agent_config, AgentConfig)
        assert agent_config.max_iterations == 7
        assert agent_config.timeout == 90.0

    # ========================================
    # 에지 케이스 테스트
    # ========================================

    def test_create_with_missing_mcp_section(
        self,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        mcp 섹션이 없는 경우 None 반환

        설정에 mcp 섹션 자체가 없는 경우
        None을 반환하는지 확인합니다.
        """
        # Given: mcp 섹션이 없는 설정
        empty_config: dict = {}

        # When: 빈 설정으로 create() 호출
        result = AgentFactory.create(
            config=empty_config,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: None 반환 (mcp.enabled 기본값 False로 처리)
        assert result is None

    def test_create_with_partial_agent_config(
        self,
        mock_llm_client: MagicMock,
        mock_mcp_server: MagicMock,
    ) -> None:
        """
        일부 에이전트 설정만 있는 경우

        agent 섹션에 일부 설정만 있을 때
        나머지는 기본값으로 처리되는지 확인합니다.
        """
        # Given: 일부 설정만 있음
        partial_config = {
            "mcp": {
                "enabled": True,
                "agent": {
                    "max_tool_calls": 3,
                    # 다른 설정은 없음
                },
            }
        }

        # When: 부분 설정으로 create() 호출
        orchestrator = AgentFactory.create(
            config=partial_config,
            llm_client=mock_llm_client,
            mcp_server=mock_mcp_server,
        )

        # Then: Orchestrator 생성됨
        assert orchestrator is not None
        # Then: 지정된 값 적용
        assert orchestrator._config.max_iterations == 3
        # Then: 나머지는 기본값
        assert orchestrator._config.fallback_tool == "search_weaviate"


class TestAgentFactoryIntegration:
    """AgentFactory 통합 테스트 (실제 컴포넌트 사용)"""

    @pytest.fixture
    def mock_llm_client_with_async(self) -> MagicMock:
        """비동기 generate_text를 지원하는 Mock LLM 클라이언트"""

        client = MagicMock()
        # 비동기 메서드 시뮬레이션
        async def async_generate_text(**kwargs):
            return '{"reasoning": "test", "tool_calls": [], "should_continue": false}'

        client.generate_text = async_generate_text
        return client

    @pytest.fixture
    def full_config(self) -> dict:
        """전체 MCP 설정 (mcp.yaml 구조)"""
        return {
            "mcp": {
                "enabled": True,
                "server_name": "test-rag-system",
                "default_timeout": 30,
                "max_concurrent_tools": 3,
                "tools": {
                    "search_vector_db": {
                        "enabled": True,
                        "description": "벡터 DB 검색",
                        "timeout": 15,
                    },
                    "query_sql": {
                        "enabled": True,
                        "description": "SQL 검색",
                        "timeout": 20,
                    },
                },
                "agent": {
                    "tool_selection": "llm",
                    "selector_model": "google/gemini-2.5-flash-lite",
                    "max_tool_calls": 5,
                    "fallback_tool": "search_vector_db",
                },
            }
        }

    def test_orchestrator_components_initialized(
        self,
        full_config: dict,
        mock_llm_client_with_async: MagicMock,
    ) -> None:
        """
        Orchestrator의 모든 컴포넌트가 올바르게 초기화되는지 확인

        Planner, Executor, Synthesizer가 올바르게 생성되고
        Orchestrator에 주입되는지 검증합니다.
        """
        # Given: 실제 MCP 서버 Mock
        mock_mcp_server = MagicMock()
        mock_mcp_server.is_enabled = True
        mock_mcp_server.get_tool_schemas = MagicMock(return_value=[])

        # When: Orchestrator 생성
        orchestrator = AgentFactory.create(
            config=full_config,
            llm_client=mock_llm_client_with_async,
            mcp_server=mock_mcp_server,
        )

        # Then: 모든 컴포넌트가 초기화됨
        assert orchestrator is not None
        # 내부 컴포넌트 확인 (private 속성)
        assert hasattr(orchestrator, "_planner")
        assert hasattr(orchestrator, "_executor")
        assert hasattr(orchestrator, "_synthesizer")
        assert hasattr(orchestrator, "_config")
        assert orchestrator._planner is not None
        assert orchestrator._executor is not None
        assert orchestrator._synthesizer is not None
