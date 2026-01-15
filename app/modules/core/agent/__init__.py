"""
Agent 모듈 - Agentic RAG Orchestrator

LLM 기반 도구 선택과 다단계 실행을 지원하는 에이전트 시스템.
ReAct 패턴 (Reasoning + Acting + Synthesizing) 기반으로 구현되었습니다.

주요 컴포넌트:
- AgentConfig: 에이전트 설정 (mcp.yaml과 매핑)
- ToolCall: 도구 호출 요청
- ToolResult: 도구 실행 결과
- AgentStep: ReAct 패턴 한 사이클
- AgentState: 에이전트 메모리 (히스토리 관리)
- AgentResult: 최종 결과
- ReflectionResult: Self-Reflection 결과
- AgentPlanner: LLM 기반 도구 선택 (Reasoning 담당)
- AgentExecutor: 도구 실행 (Acting 담당)
- AgentSynthesizer: 결과 합성 (Synthesize 담당)
- AgentReflector: 답변 품질 평가 (Reflect 담당)
- AgentOrchestrator: 메인 에이전트 루프 (전체 조율)
- AgentFactory: 설정 기반 Orchestrator 생성 팩토리

사용 예시 (Factory 사용 - 권장):
    from app.modules.core.agent import AgentFactory, AgentOrchestrator

    # 팩토리를 통한 생성 (DI Container에서 사용)
    orchestrator = AgentFactory.create(
        config=config,
        llm_client=llm_client,
        mcp_server=mcp_server,
    )

    # 실행
    result = await orchestrator.run("검색해줘")

사용 예시 (Orchestrator 직접 사용):
    from app.modules.core.agent import AgentOrchestrator

    # Orchestrator를 통한 전체 실행
    orchestrator = AgentOrchestrator(
        planner=planner,
        executor=executor,
        synthesizer=synthesizer,
        config=config,
    )
    result = await orchestrator.run("사용자 질문")

사용 예시 (개별 컴포넌트 사용):
    from app.modules.core.agent import (
        AgentConfig,
        AgentState,
        AgentPlanner,
        AgentExecutor,
        AgentSynthesizer,
        ToolCall,
        ToolResult,
    )

    # 설정 생성
    config = AgentConfig(max_iterations=5)

    # 상태 초기화
    state = AgentState(original_query="검색해줘")

    # Planner를 통한 도구 선택
    planner = AgentPlanner(llm_client, mcp_server, config)
    tool_calls, reasoning, should_continue = await planner.plan(state)

    # Executor를 통한 도구 실행
    executor = AgentExecutor(mcp_server, config)
    results = await executor.execute(tool_calls)

    # Synthesizer를 통한 결과 합성
    synthesizer = AgentSynthesizer(llm_client, config)
    answer, sources = await synthesizer.synthesize(state)
"""

from .executor import AgentExecutor
from .factory import AgentFactory
from .interfaces import (
    AgentConfig,
    AgentResult,
    AgentState,
    AgentStep,
    ReflectionResult,
    ToolCall,
    ToolResult,
)
from .orchestrator import AgentOrchestrator
from .planner import AgentPlanner
from .reflector import AgentReflector
from .synthesizer import AgentSynthesizer

__all__ = [
    # 설정
    "AgentConfig",
    # 도구 관련
    "ToolCall",
    "ToolResult",
    # 에이전트 상태
    "AgentStep",
    "AgentState",
    # 결과
    "AgentResult",
    "ReflectionResult",
    # 컴포넌트
    "AgentPlanner",
    "AgentExecutor",
    "AgentSynthesizer",
    "AgentReflector",
    "AgentOrchestrator",
    # 팩토리
    "AgentFactory",
]
