"""
Agent 인터페이스 및 데이터 클래스 테스트

ReAct 패턴 기반 에이전트 시스템의 핵심 타입 정의를 검증합니다.
"""

from dataclasses import asdict


class TestAgentConfig:
    """AgentConfig 테스트 - 에이전트 설정 데이터 클래스"""

    def test_agent_config_defaults(self):
        """기본값으로 AgentConfig 생성 테스트"""
        from app.modules.core.agent.interfaces import AgentConfig

        config = AgentConfig()

        # 기본값 검증
        assert config.max_iterations == 5
        assert config.tool_selection == "llm"
        assert config.selector_model == "google/gemini-2.5-flash-lite"
        assert config.fallback_tool == "search_weaviate"
        assert config.timeout == 60.0
        assert config.tool_timeout == 15.0
        assert config.parallel_execution is True

    def test_agent_config_custom_values(self):
        """커스텀 값으로 AgentConfig 생성 테스트"""
        from app.modules.core.agent.interfaces import AgentConfig

        config = AgentConfig(
            max_iterations=10,
            tool_selection="hybrid",
            timeout=120.0,
            parallel_execution=False,
        )

        assert config.max_iterations == 10
        assert config.tool_selection == "hybrid"
        assert config.timeout == 120.0
        assert config.parallel_execution is False

    def test_agent_config_asdict(self):
        """AgentConfig를 딕셔너리로 변환 테스트"""
        from app.modules.core.agent.interfaces import AgentConfig

        config = AgentConfig()
        config_dict = asdict(config)

        assert isinstance(config_dict, dict)
        assert "max_iterations" in config_dict
        assert "tool_selection" in config_dict


class TestToolCall:
    """ToolCall 테스트 - 도구 호출 요청 데이터 클래스"""

    def test_tool_call_creation(self):
        """ToolCall 생성 테스트"""
        from app.modules.core.agent.interfaces import ToolCall

        tool_call = ToolCall(
            tool_name="search_weaviate",
            arguments={"query": "테스트 검색", "top_k": 5},
        )

        assert tool_call.tool_name == "search_weaviate"
        assert tool_call.arguments["query"] == "테스트 검색"
        assert tool_call.arguments["top_k"] == 5
        # call_id는 UUID로 자동 생성되어야 함
        assert tool_call.call_id is not None
        assert len(tool_call.call_id) == 8  # UUID 앞 8자리

    def test_tool_call_with_custom_id(self):
        """커스텀 call_id로 ToolCall 생성 테스트"""
        from app.modules.core.agent.interfaces import ToolCall

        tool_call = ToolCall(
            tool_name="query_sql",
            arguments={"question": "매출 조회"},
            call_id="custom-id",
        )

        assert tool_call.call_id == "custom-id"

    def test_tool_call_with_reasoning(self):
        """reasoning 포함 ToolCall 생성 테스트"""
        from app.modules.core.agent.interfaces import ToolCall

        tool_call = ToolCall(
            tool_name="search_weaviate",
            arguments={"query": "테스트"},
            reasoning="사용자가 정보를 검색하려고 합니다",
        )

        assert tool_call.reasoning == "사용자가 정보를 검색하려고 합니다"


class TestToolResult:
    """ToolResult 테스트 - 도구 실행 결과 데이터 클래스"""

    def test_tool_result_success(self):
        """성공한 도구 결과 테스트"""
        from app.modules.core.agent.interfaces import ToolResult

        result = ToolResult(
            call_id="test-id",
            tool_name="search_weaviate",
            success=True,
            data={"documents": [{"content": "결과"}]},
        )

        assert result.success is True
        assert result.data is not None
        assert result.error is None
        assert result.execution_time == 0.0

    def test_tool_result_failure(self):
        """실패한 도구 결과 테스트"""
        from app.modules.core.agent.interfaces import ToolResult

        result = ToolResult(
            call_id="test-id",
            tool_name="search_weaviate",
            success=False,
            error="타임아웃 발생",
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "타임아웃 발생"

    def test_tool_result_with_execution_time(self):
        """실행 시간 포함 도구 결과 테스트"""
        from app.modules.core.agent.interfaces import ToolResult

        result = ToolResult(
            call_id="test-id",
            tool_name="search_weaviate",
            success=True,
            data={"documents": []},
            execution_time=1.5,
        )

        assert result.execution_time == 1.5


class TestAgentStep:
    """AgentStep 테스트 - ReAct 패턴 한 사이클"""

    def test_agent_step_creation(self):
        """AgentStep 생성 테스트"""
        from app.modules.core.agent.interfaces import (
            AgentStep,
            ToolCall,
            ToolResult,
        )

        tool_call = ToolCall(
            tool_name="search_weaviate",
            arguments={"query": "테스트"},
        )
        tool_result = ToolResult(
            call_id=tool_call.call_id,
            tool_name="search_weaviate",
            success=True,
            data={"documents": []},
        )

        step = AgentStep(
            step_number=1,
            reasoning="검색이 필요합니다",
            tool_calls=[tool_call],
            tool_results=[tool_result],
        )

        assert step.step_number == 1
        assert len(step.tool_calls) == 1
        assert len(step.tool_results) == 1
        assert step.should_continue is True  # 기본값
        assert step.duration == 0.0  # 기본값

    def test_agent_step_with_should_continue_false(self):
        """종료 조건 AgentStep 테스트"""
        from app.modules.core.agent.interfaces import AgentStep

        step = AgentStep(
            step_number=2,
            reasoning="더 이상 검색이 필요 없습니다",
            tool_calls=[],
            tool_results=[],
            should_continue=False,
            duration=2.5,
        )

        assert step.should_continue is False
        assert step.duration == 2.5


class TestAgentState:
    """AgentState 테스트 - 에이전트 메모리 (히스토리 관리)"""

    def test_agent_state_initial(self):
        """초기 상태 테스트"""
        from app.modules.core.agent.interfaces import AgentState

        state = AgentState(
            original_query="테스트 질문",
        )

        assert state.original_query == "테스트 질문"
        assert state.status == "pending"
        assert len(state.steps) == 0
        assert state.final_answer is None
        assert len(state.sources) == 0
        assert state.error is None

    def test_agent_state_add_step(self):
        """스텝 추가 테스트"""
        from app.modules.core.agent.interfaces import AgentState, AgentStep

        state = AgentState(original_query="테스트")

        step = AgentStep(
            step_number=1,
            reasoning="테스트 이유",
            tool_calls=[],
            tool_results=[],
        )
        state.steps.append(step)
        state.status = "running"

        assert len(state.steps) == 1
        assert state.status == "running"

    def test_agent_state_current_iteration(self):
        """현재 반복 횟수 프로퍼티 테스트"""
        from app.modules.core.agent.interfaces import AgentState, AgentStep

        state = AgentState(original_query="테스트")

        assert state.current_iteration == 0

        # 스텝 2개 추가
        for i in range(1, 3):
            state.steps.append(AgentStep(
                step_number=i,
                reasoning=f"스텝 {i}",
                tool_calls=[],
                tool_results=[],
            ))

        assert state.current_iteration == 2

    def test_agent_state_all_tool_results(self):
        """모든 도구 결과 평탄화 테스트"""
        from app.modules.core.agent.interfaces import (
            AgentState,
            AgentStep,
            ToolResult,
        )

        state = AgentState(original_query="테스트")

        # 여러 스텝에 여러 결과 추가
        state.steps.append(AgentStep(
            step_number=1,
            reasoning="1단계",
            tool_calls=[],
            tool_results=[
                ToolResult(call_id="1", tool_name="tool1", success=True),
                ToolResult(call_id="2", tool_name="tool2", success=True),
            ],
        ))
        state.steps.append(AgentStep(
            step_number=2,
            reasoning="2단계",
            tool_calls=[],
            tool_results=[
                ToolResult(call_id="3", tool_name="tool3", success=True),
            ],
        ))

        all_results = state.all_tool_results

        assert len(all_results) == 3
        assert all_results[0].tool_name == "tool1"
        assert all_results[2].tool_name == "tool3"

    def test_agent_state_get_context_for_llm(self):
        """LLM 컨텍스트 생성 테스트"""
        from app.modules.core.agent.interfaces import (
            AgentState,
            AgentStep,
            ToolResult,
        )

        state = AgentState(original_query="테스트")

        # 빈 상태
        assert state.get_context_for_llm() == ""

        # 스텝 추가
        state.steps.append(AgentStep(
            step_number=1,
            reasoning="검색 수행",
            tool_calls=[],
            tool_results=[
                ToolResult(
                    call_id="1",
                    tool_name="search_weaviate",
                    success=True,
                ),
            ],
        ))

        context = state.get_context_for_llm()

        assert "Step 1" in context
        assert "검색 수행" in context
        assert "search_weaviate" in context
        assert "성공" in context

    def test_agent_state_get_context_with_failure(self):
        """실패 결과 포함 컨텍스트 테스트"""
        from app.modules.core.agent.interfaces import (
            AgentState,
            AgentStep,
            ToolResult,
        )

        state = AgentState(original_query="테스트")

        state.steps.append(AgentStep(
            step_number=1,
            reasoning="검색 시도",
            tool_calls=[],
            tool_results=[
                ToolResult(
                    call_id="1",
                    tool_name="search_weaviate",
                    success=False,
                    error="타임아웃",
                ),
            ],
        ))

        context = state.get_context_for_llm()

        assert "실패" in context
        assert "타임아웃" in context


class TestAgentResult:
    """AgentResult 테스트 - 에이전트 최종 결과"""

    def test_agent_result_success(self):
        """성공 결과 테스트"""
        from app.modules.core.agent.interfaces import AgentResult

        result = AgentResult(
            success=True,
            answer="최종 답변입니다",
            sources=[{"title": "문서1", "source": "doc1.md"}],
            steps_taken=3,
            total_time=2.5,
        )

        assert result.success is True
        assert result.answer == "최종 답변입니다"
        assert len(result.sources) == 1
        assert result.steps_taken == 3
        assert result.total_time == 2.5
        assert result.error is None

    def test_agent_result_failure(self):
        """실패 결과 테스트"""
        from app.modules.core.agent.interfaces import AgentResult

        result = AgentResult(
            success=False,
            answer="죄송합니다. 처리 중 오류가 발생했습니다.",
            error="LLM 호출 실패",
            steps_taken=1,
            total_time=0.5,
        )

        assert result.success is False
        assert result.error == "LLM 호출 실패"

    def test_agent_result_with_tools_used(self):
        """사용된 도구 목록 포함 결과 테스트"""
        from app.modules.core.agent.interfaces import AgentResult

        result = AgentResult(
            success=True,
            answer="답변",
            tools_used=["search_weaviate", "query_sql"],
            steps_taken=2,
            total_time=3.0,
        )

        assert len(result.tools_used) == 2
        assert "search_weaviate" in result.tools_used
        assert "query_sql" in result.tools_used

    def test_agent_result_with_debug_info(self):
        """디버그 정보 포함 결과 테스트"""
        from app.modules.core.agent.interfaces import AgentResult

        result = AgentResult(
            success=True,
            answer="답변",
            steps_taken=1,
            total_time=1.0,
            debug_info={"model": "gemini-2.5-flash", "tokens": 1500},
        )

        assert "model" in result.debug_info
        assert result.debug_info["tokens"] == 1500


class TestModuleImport:
    """모듈 임포트 테스트"""

    def test_import_from_module(self):
        """모듈에서 직접 임포트 테스트"""
        from app.modules.core.agent import (
            AgentConfig,
            AgentResult,
            AgentState,
            AgentStep,
            ToolCall,
            ToolResult,
        )

        # 임포트가 성공하면 테스트 통과
        assert AgentConfig is not None
        assert ToolCall is not None
        assert ToolResult is not None
        assert AgentStep is not None
        assert AgentState is not None
        assert AgentResult is not None
