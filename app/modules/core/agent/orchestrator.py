"""
AgentOrchestrator - 메인 에이전트 루프

ReAct 패턴 기반 에이전트 루프를 조율하는 핵심 컴포넌트입니다.
Plan -> Execute -> Observe -> Synthesize 사이클을 반복하며
최종 답변을 생성합니다.

주요 기능:
- AgentPlanner를 통한 도구 선택 (Plan)
- AgentExecutor를 통한 도구 실행 (Execute)
- 결과 관찰 및 다음 행동 결정 (Observe)
- AgentSynthesizer를 통한 최종 답변 생성 (Synthesize)
- max_iterations로 무한 루프 방지
- AgentResult 생성 및 반환

사용 예시:
    orchestrator = AgentOrchestrator(
        planner=planner,
        executor=executor,
        synthesizer=synthesizer,
        config=config,
    )
    result = await orchestrator.run("사용자 질문")

아키텍처:
    ┌─────────────────────────────────────────────────────────┐
    │                   AgentOrchestrator                      │
    │                                                          │
    │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐ │
    │  │  Plan   │──▶│ Execute │──▶│ Observe │──▶│Synthesize│ │
    │  │(Planner)│   │(Executor)│   │ (State) │   │(Synth)  │ │
    │  └─────────┘   └─────────┘   └─────────┘   └─────────┘ │
    │       │                            │                     │
    │       └────────── 반복 ────────────┘                     │
    │              (until done or max)                         │
    └─────────────────────────────────────────────────────────┘
"""

import time

from app.lib.logger import get_logger
from app.modules.core.agent.executor import AgentExecutor
from app.modules.core.agent.interfaces import (
    AgentConfig,
    AgentResult,
    AgentState,
    AgentStep,
)
from app.modules.core.agent.planner import AgentPlanner
from app.modules.core.agent.synthesizer import AgentSynthesizer

logger = get_logger(__name__)


class AgentOrchestrator:
    """
    에이전트 오케스트레이터

    ReAct 패턴 기반 에이전트 루프를 실행하는 핵심 컴포넌트입니다.
    Plan -> Execute -> Observe -> Synthesize 사이클을 반복하며
    최종 답변을 생성합니다.

    Attributes:
        _planner: 도구 선택기 (AgentPlanner)
        _executor: 도구 실행기 (AgentExecutor)
        _synthesizer: 결과 합성기 (AgentSynthesizer)
        _config: 에이전트 설정 (AgentConfig)

    흐름:
        1. Planner: 다음 행동 결정 (도구 선택)
        2. Executor: 도구 실행
        3. Observe: 결과 확인 -> 계속/종료 결정
        4. Synthesizer: 최종 답변 생성
    """

    def __init__(
        self,
        planner: AgentPlanner,
        executor: AgentExecutor,
        synthesizer: AgentSynthesizer,
        config: AgentConfig,
    ) -> None:
        """
        AgentOrchestrator 초기화

        Args:
            planner: 도구 선택기 (LLM 기반)
            executor: 도구 실행기 (MCPServer 래핑)
            synthesizer: 결과 합성기 (최종 답변 생성)
            config: 에이전트 설정 (max_iterations, timeout 등)

        Raises:
            ValueError: 필수 의존성 누락 시
        """
        if planner is None:
            raise ValueError("planner는 필수입니다")
        if executor is None:
            raise ValueError("executor는 필수입니다")
        if synthesizer is None:
            raise ValueError("synthesizer는 필수입니다")
        if config is None:
            raise ValueError("config는 필수입니다")

        self._planner = planner
        self._executor = executor
        self._synthesizer = synthesizer
        self._config = config

        logger.info(
            f"AgentOrchestrator 초기화: "
            f"max_iterations={config.max_iterations}, "
            f"timeout={config.timeout}s"
        )

    async def run(
        self,
        query: str,
        session_context: str = "",
    ) -> AgentResult:
        """
        에이전트 루프 실행

        사용자 쿼리를 받아 ReAct 루프를 실행하고
        최종 결과를 AgentResult로 반환합니다.

        Args:
            query: 사용자 질문
            session_context: 세션 컨텍스트 (이전 대화 내용, 선택적)

        Returns:
            AgentResult: 최종 결과 (성공 여부, 답변, 소스 등)

        Note:
            - max_iterations에 도달하면 현재까지의 결과로 답변 생성
            - 예외 발생 시 실패 결과 반환
        """
        start_time = time.time()

        # 상태 초기화
        state = AgentState(original_query=query)
        state.status = "running"

        # 세션 컨텍스트가 있으면 로깅 (향후 AgentState 확장 시 활용)
        if session_context:
            logger.debug(f"세션 컨텍스트: {session_context[:100]}...")

        logger.info(f"Agent 시작: {query[:50]}...")

        try:
            # 메인 ReAct 루프
            while state.current_iteration < self._config.max_iterations:
                step_start = time.time()
                iteration = state.current_iteration + 1

                logger.info(
                    f"Step {iteration}/{self._config.max_iterations}"
                )

                # 1. Plan: 다음 행동 결정 (도구 선택)
                tool_calls, reasoning, should_continue = await self._planner.plan(
                    state
                )

                # 2. Execute: 도구 실행
                tool_results = []
                if tool_calls:
                    tool_results = await self._executor.execute(tool_calls)

                # 3. Observe: 스텝 기록
                step = AgentStep(
                    step_number=iteration,
                    reasoning=reasoning,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    should_continue=should_continue,
                    duration=time.time() - step_start,
                )
                state.steps.append(step)

                logger.debug(
                    f"Step {iteration} 완료: "
                    f"도구={len(tool_calls)}개, "
                    f"should_continue={should_continue}"
                )

                # 4. 종료 조건 확인
                if not should_continue:
                    logger.info(
                        f"Agent 종료 (should_continue=False, step={iteration})"
                    )
                    break

            # 최대 반복 도달 확인
            if state.current_iteration >= self._config.max_iterations:
                logger.warning(
                    f"최대 반복 횟수 도달 ({self._config.max_iterations})"
                )
                state.status = "max_iterations"

            # 5. Synthesize: 최종 답변 생성
            answer, sources = await self._synthesizer.synthesize(state)

            # 상태 업데이트
            state.final_answer = answer
            state.sources = sources
            state.status = "completed"

            # 결과 생성
            total_time = time.time() - start_time
            tools_used = self._collect_tools_used(state)

            logger.info(
                f"Agent 완료: {state.current_iteration}스텝, "
                f"{total_time:.2f}초, {len(tools_used)}개 도구 사용"
            )

            return AgentResult(
                success=True,
                answer=answer,
                sources=sources,
                steps_taken=state.current_iteration,
                total_time=total_time,
                tools_used=tools_used,
            )

        except Exception as e:
            # 에러 처리
            logger.error(f"Agent 에러: {e}", exc_info=True)

            state.status = "failed"
            state.error = str(e)

            return AgentResult(
                success=False,
                answer="죄송합니다. 처리 중 오류가 발생했습니다.",
                error=str(e),
                steps_taken=state.current_iteration,
                total_time=time.time() - start_time,
            )

    def _collect_tools_used(self, state: AgentState) -> list[str]:
        """
        사용된 도구 목록 수집

        모든 스텝에서 사용된 도구 이름을 중복 제거하여 반환합니다.

        Args:
            state: 에이전트 상태

        Returns:
            사용된 도구 이름 리스트 (중복 제거)
        """
        tools_used: set[str] = set()

        for step in state.steps:
            for tool_call in step.tool_calls:
                tools_used.add(tool_call.tool_name)

        return list(tools_used)
