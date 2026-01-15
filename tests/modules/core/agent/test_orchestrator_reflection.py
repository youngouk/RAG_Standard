"""
AgentOrchestrator Self-Reflection 통합 테스트

Self-Reflection 루프가 Orchestrator에 올바르게 통합되었는지 검증:
- Reflection 활성화/비활성화
- 점수 기반 재시도 로직
- 최대 반복 횟수 제한
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.modules.core.agent.orchestrator import AgentOrchestrator
from app.modules.core.agent.interfaces import (
    AgentConfig,
    ReflectionResult,
)


class TestOrchestratorReflection:
    """AgentOrchestrator Reflection 통합 테스트"""

    @pytest.fixture
    def mock_planner(self):
        """Mock Planner - 검색 완료 상태 반환"""
        planner = AsyncMock()
        planner.plan.return_value = ([], "검색 완료", False)
        return planner

    @pytest.fixture
    def mock_executor(self):
        """Mock Executor - 빈 결과 반환"""
        executor = AsyncMock()
        executor.execute.return_value = []
        return executor

    @pytest.fixture
    def mock_synthesizer(self):
        """Mock Synthesizer - 테스트 답변 반환"""
        synthesizer = AsyncMock()
        synthesizer.synthesize.return_value = ("테스트 답변", [])
        return synthesizer

    @pytest.fixture
    def mock_reflector_high_score(self):
        """Mock Reflector - 높은 점수 반환"""
        reflector = AsyncMock()
        reflector.reflect.return_value = ReflectionResult(
            score=9.0,
            needs_improvement=False,
            issues=[],
            suggestions=[],
            reasoning="좋은 답변"
        )
        return reflector

    @pytest.fixture
    def config_with_reflection(self):
        """Reflection 활성화 설정"""
        return AgentConfig(
            enable_reflection=True,
            reflection_threshold=7.0,
            max_reflection_iterations=2
        )

    @pytest.fixture
    def config_without_reflection(self):
        """Reflection 비활성화 설정"""
        return AgentConfig(enable_reflection=False)

    @pytest.mark.asyncio
    async def test_orchestrator_with_reflection_high_score(
        self, mock_planner, mock_executor, mock_synthesizer,
        mock_reflector_high_score, config_with_reflection
    ):
        """높은 점수면 반복 없이 완료"""
        # Given: Reflection 활성화된 Orchestrator
        orchestrator = AgentOrchestrator(
            planner=mock_planner,
            executor=mock_executor,
            synthesizer=mock_synthesizer,
            config=config_with_reflection,
            reflector=mock_reflector_high_score,
        )

        # When: 실행
        result = await orchestrator.run("테스트 질문")

        # Then: 성공, Reflection 1회 호출, Synthesizer 1회 호출
        assert result.success is True
        assert mock_reflector_high_score.reflect.call_count == 1
        assert mock_synthesizer.synthesize.call_count == 1

    @pytest.mark.asyncio
    async def test_orchestrator_with_reflection_low_score_retry(
        self, mock_planner, mock_executor, config_with_reflection
    ):
        """낮은 점수면 재시도"""
        # Given: 첫 번째: 낮은 점수, 두 번째: 높은 점수
        mock_reflector = AsyncMock()
        mock_reflector.reflect.side_effect = [
            ReflectionResult(
                score=4.0, needs_improvement=True,
                issues=["정보 부족"], suggestions=["추가 검색"],
                reasoning="부족"
            ),
            ReflectionResult(
                score=9.0, needs_improvement=False,
                issues=[], suggestions=[],
                reasoning="개선됨"
            ),
        ]

        # Synthesizer도 두 번 호출됨
        mock_synthesizer = AsyncMock()
        mock_synthesizer.synthesize.side_effect = [
            ("첫 번째 답변", []),
            ("개선된 답변", []),
        ]

        orchestrator = AgentOrchestrator(
            planner=mock_planner,
            executor=mock_executor,
            synthesizer=mock_synthesizer,
            config=config_with_reflection,
            reflector=mock_reflector,
        )

        # When: 실행
        result = await orchestrator.run("테스트 질문")

        # Then: 성공, Reflection 2회 호출, 개선된 답변 반환
        assert result.success is True
        assert mock_reflector.reflect.call_count == 2
        assert "개선된 답변" in result.answer

    @pytest.mark.asyncio
    async def test_orchestrator_reflection_disabled(
        self, mock_planner, mock_executor, mock_synthesizer,
        mock_reflector_high_score, config_without_reflection
    ):
        """Reflection 비활성화 시 건너뜀"""
        # Given: Reflection 비활성화
        orchestrator = AgentOrchestrator(
            planner=mock_planner,
            executor=mock_executor,
            synthesizer=mock_synthesizer,
            config=config_without_reflection,
            reflector=mock_reflector_high_score,
        )

        # When: 실행
        result = await orchestrator.run("테스트 질문")

        # Then: 성공, Reflection 호출 안됨
        assert result.success is True
        assert mock_reflector_high_score.reflect.call_count == 0

    @pytest.mark.asyncio
    async def test_orchestrator_max_reflection_iterations(
        self, mock_planner, mock_executor, mock_synthesizer
    ):
        """최대 반복 횟수 초과 시 중단"""
        # Given: 계속 낮은 점수 반환
        mock_reflector = AsyncMock()
        mock_reflector.reflect.return_value = ReflectionResult(
            score=3.0, needs_improvement=True,
            issues=["계속 부족"], suggestions=[],
            reasoning="부족"
        )

        config = AgentConfig(
            enable_reflection=True,
            reflection_threshold=7.0,
            max_reflection_iterations=2  # 최대 2회
        )

        orchestrator = AgentOrchestrator(
            planner=mock_planner,
            executor=mock_executor,
            synthesizer=mock_synthesizer,
            config=config,
            reflector=mock_reflector,
        )

        # When: 실행
        result = await orchestrator.run("테스트 질문")

        # Then: 최대 2회까지만 반복
        assert mock_reflector.reflect.call_count == 2
        assert result.success is True

    @pytest.mark.asyncio
    async def test_orchestrator_without_reflector(
        self, mock_planner, mock_executor, mock_synthesizer,
        config_with_reflection
    ):
        """Reflector 없으면 Reflection 건너뜀 (하위 호환성)"""
        # Given: reflector=None
        orchestrator = AgentOrchestrator(
            planner=mock_planner,
            executor=mock_executor,
            synthesizer=mock_synthesizer,
            config=config_with_reflection,
            reflector=None,  # Reflector 없음
        )

        # When: 실행
        result = await orchestrator.run("테스트 질문")

        # Then: 성공 (Reflection 없이 정상 동작)
        assert result.success is True
