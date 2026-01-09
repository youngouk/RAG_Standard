"""
AgentSynthesizer 테스트 - 결과 합성

ReAct 패턴에서 "Synthesize" 담당 컴포넌트의 테스트.
도구 실행 결과들을 분석하여 최종 답변을 생성합니다.

테스트 시나리오:
1. 성공적인 답변 생성
2. 소스 정보 추출
3. 실패한 결과 처리
4. 빈 상태 처리
5. 여러 스텝의 결과 통합
"""

from unittest.mock import AsyncMock

import pytest

from app.modules.core.agent.interfaces import (
    AgentConfig,
    AgentState,
    AgentStep,
    ToolCall,
    ToolResult,
)
from app.modules.core.agent.synthesizer import AgentSynthesizer


class TestAgentSynthesizer:
    """AgentSynthesizer 테스트"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 클라이언트"""
        client = AsyncMock()
        client.generate_text = AsyncMock()
        return client

    @pytest.fixture
    def agent_config(self):
        """에이전트 설정"""
        return AgentConfig()

    @pytest.fixture
    def synthesizer(self, mock_llm_client, agent_config):
        """AgentSynthesizer 인스턴스"""
        return AgentSynthesizer(
            llm_client=mock_llm_client,
            config=agent_config,
        )

    def _create_state_with_results(self) -> AgentState:
        """테스트용 성공 결과가 있는 상태 생성"""
        state = AgentState(original_query="파이썬 튜토리얼 알려줘")

        tool_call = ToolCall(
            tool_name="search_weaviate",
            arguments={"query": "파이썬"},
        )
        tool_result = ToolResult(
            call_id=tool_call.call_id,
            tool_name="search_weaviate",
            success=True,
            data={
                "documents": [
                    {
                        "content": "파이썬 기초 강좌입니다",
                        "metadata": {"source": "doc1.md", "title": "파이썬 기초"},
                    },
                    {
                        "content": "파이썬 고급 문법",
                        "metadata": {"source": "doc2.md", "title": "파이썬 고급"},
                    },
                ]
            },
        )

        state.steps.append(
            AgentStep(
                step_number=1,
                reasoning="검색 수행",
                tool_calls=[tool_call],
                tool_results=[tool_result],
            )
        )

        return state

    @pytest.mark.asyncio
    async def test_synthesizer_generates_answer(
        self, synthesizer, mock_llm_client
    ):
        """
        최종 답변 생성 테스트

        LLM을 사용하여 도구 결과를 바탕으로 답변을 생성해야 합니다.
        """
        # LLM 응답 설정
        mock_llm_client.generate_text.return_value = """
        파이썬 튜토리얼을 찾았습니다.

        1. 파이썬 기초 강좌 - 초보자용
        2. 파이썬 고급 문법 - 중급자용

        더 자세한 내용은 문서를 참고하세요.
        """

        state = self._create_state_with_results()

        # synthesize 호출
        answer, sources = await synthesizer.synthesize(state)

        # 검증
        assert answer is not None
        assert len(answer) > 0
        assert "파이썬" in answer
        # LLM이 호출되었는지 확인
        mock_llm_client.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesizer_extracts_sources(
        self, synthesizer, mock_llm_client
    ):
        """
        소스 추출 테스트

        도구 결과에서 메타데이터를 파싱하여 소스 정보를 추출해야 합니다.
        """
        mock_llm_client.generate_text.return_value = "답변입니다."

        state = self._create_state_with_results()

        answer, sources = await synthesizer.synthesize(state)

        # 소스가 추출되었는지 확인
        assert len(sources) == 2
        assert sources[0]["source"] == "doc1.md"
        assert sources[1]["source"] == "doc2.md"

    @pytest.mark.asyncio
    async def test_synthesizer_handles_failed_results(
        self, synthesizer, mock_llm_client
    ):
        """
        실패한 결과 처리 테스트

        도구 실행이 실패한 경우에도 적절히 처리해야 합니다.
        """
        mock_llm_client.generate_text.return_value = (
            "검색에 실패했지만, 가능한 정보를 제공합니다."
        )

        state = AgentState(original_query="테스트")
        state.steps.append(
            AgentStep(
                step_number=1,
                reasoning="검색 시도",
                tool_calls=[
                    ToolCall(tool_name="search_weaviate", arguments={})
                ],
                tool_results=[
                    ToolResult(
                        call_id="test",
                        tool_name="search_weaviate",
                        success=False,
                        error="타임아웃",
                    )
                ],
            )
        )

        answer, sources = await synthesizer.synthesize(state)

        # 실패해도 답변은 생성됨
        assert answer is not None
        # 실패한 결과에서는 소스가 없음
        assert len(sources) == 0

    @pytest.mark.asyncio
    async def test_synthesizer_handles_empty_state(
        self, synthesizer, mock_llm_client
    ):
        """
        빈 상태 처리 테스트

        도구 실행 결과가 없는 경우에도 적절히 처리해야 합니다.
        """
        mock_llm_client.generate_text.return_value = (
            "관련 정보를 찾지 못했습니다."
        )

        state = AgentState(original_query="테스트")
        # 스텝 없음 - 빈 상태

        answer, sources = await synthesizer.synthesize(state)

        assert answer is not None
        assert len(sources) == 0

    @pytest.mark.asyncio
    async def test_synthesizer_uses_all_results(
        self, synthesizer, mock_llm_client
    ):
        """
        모든 스텝의 결과 활용 테스트

        여러 스텝에 걸친 모든 도구 결과를 합성에 활용해야 합니다.
        """
        mock_llm_client.generate_text.return_value = "종합 답변입니다."

        state = AgentState(original_query="복잡한 질문")

        # 첫 번째 스텝
        state.steps.append(
            AgentStep(
                step_number=1,
                reasoning="첫 번째 검색",
                tool_calls=[
                    ToolCall(tool_name="search_weaviate", arguments={})
                ],
                tool_results=[
                    ToolResult(
                        call_id="step1",
                        tool_name="search_weaviate",
                        success=True,
                        data={
                            "documents": [
                                {
                                    "content": "첫 번째 결과",
                                    "metadata": {"source": "a.md"},
                                }
                            ]
                        },
                    )
                ],
            )
        )

        # 두 번째 스텝
        state.steps.append(
            AgentStep(
                step_number=2,
                reasoning="두 번째 검색",
                tool_calls=[ToolCall(tool_name="query_sql", arguments={})],
                tool_results=[
                    ToolResult(
                        call_id="step2",
                        tool_name="query_sql",
                        success=True,
                        data={
                            "documents": [
                                {
                                    "content": "두 번째 결과",
                                    "metadata": {"source": "b.md"},
                                }
                            ]
                        },
                    )
                ],
            )
        )

        answer, sources = await synthesizer.synthesize(state)

        # 두 스텝의 결과가 모두 포함되어야 함
        assert len(sources) == 2
        source_files = [s["source"] for s in sources]
        assert "a.md" in source_files
        assert "b.md" in source_files

    @pytest.mark.asyncio
    async def test_synthesizer_deduplicates_sources(
        self, synthesizer, mock_llm_client
    ):
        """
        중복 소스 제거 테스트

        같은 소스가 여러 번 나와도 한 번만 포함되어야 합니다.
        """
        mock_llm_client.generate_text.return_value = "답변입니다."

        state = AgentState(original_query="테스트")
        state.steps.append(
            AgentStep(
                step_number=1,
                reasoning="검색",
                tool_calls=[
                    ToolCall(tool_name="search_weaviate", arguments={})
                ],
                tool_results=[
                    ToolResult(
                        call_id="test",
                        tool_name="search_weaviate",
                        success=True,
                        data={
                            "documents": [
                                {
                                    "content": "내용1",
                                    "metadata": {"source": "same.md"},
                                },
                                {
                                    "content": "내용2",
                                    "metadata": {"source": "same.md"},
                                },
                                {
                                    "content": "내용3",
                                    "metadata": {"source": "different.md"},
                                },
                            ]
                        },
                    )
                ],
            )
        )

        answer, sources = await synthesizer.synthesize(state)

        # 중복 제거되어 2개만 남아야 함
        assert len(sources) == 2
        source_files = [s["source"] for s in sources]
        assert "same.md" in source_files
        assert "different.md" in source_files

    @pytest.mark.asyncio
    async def test_synthesizer_handles_llm_error(
        self, synthesizer, mock_llm_client
    ):
        """
        LLM 에러 처리 테스트

        LLM 호출 실패 시 적절한 에러 메시지를 반환해야 합니다.
        """
        mock_llm_client.generate_text.side_effect = Exception("LLM 에러")

        state = self._create_state_with_results()

        answer, sources = await synthesizer.synthesize(state)

        # 에러 발생해도 기본 응답 반환
        assert answer is not None
        assert "오류" in answer or "죄송" in answer

    @pytest.mark.asyncio
    async def test_synthesizer_initialization_validation(self, agent_config):
        """
        초기화 유효성 검사 테스트

        필수 의존성이 없으면 에러가 발생해야 합니다.
        """
        with pytest.raises(ValueError, match="llm_client"):
            AgentSynthesizer(llm_client=None, config=agent_config)

    @pytest.mark.asyncio
    async def test_synthesizer_limits_content_length(
        self, synthesizer, mock_llm_client
    ):
        """
        결과 내용 길이 제한 테스트

        너무 긴 내용은 적절히 잘라서 LLM에 전달해야 합니다.
        """
        mock_llm_client.generate_text.return_value = "요약 답변"

        state = AgentState(original_query="테스트")
        # 매우 긴 내용 생성
        long_content = "A" * 10000
        state.steps.append(
            AgentStep(
                step_number=1,
                reasoning="검색",
                tool_calls=[
                    ToolCall(tool_name="search_weaviate", arguments={})
                ],
                tool_results=[
                    ToolResult(
                        call_id="test",
                        tool_name="search_weaviate",
                        success=True,
                        data={
                            "documents": [
                                {
                                    "content": long_content,
                                    "metadata": {"source": "test.md"},
                                }
                            ]
                        },
                    )
                ],
            )
        )

        answer, sources = await synthesizer.synthesize(state)

        # 정상적으로 처리되어야 함
        assert answer is not None
        # LLM에 전달된 프롬프트 확인
        call_args = mock_llm_client.generate_text.call_args
        prompt = call_args.kwargs.get("prompt", "")
        # 전달된 내용이 원본보다 짧아야 함 (잘림)
        assert len(prompt) < len(long_content) + 1000
