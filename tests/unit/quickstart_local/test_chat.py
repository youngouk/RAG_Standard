"""
Rich CLI 챗봇 단위 테스트

CLI 챗봇의 핵심 함수를 테스트합니다.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestChatHelpers:
    """CLI 챗봇 헬퍼 함수 테스트"""

    @pytest.mark.asyncio
    async def test_search_documents_calls_retriever(self):
        """
        검색 함수가 ChromaRetriever를 올바르게 호출하는지 확인

        Given: Mock retriever
        When: search_documents() 호출
        Then: retriever.search()가 쿼리와 함께 호출됨
        """
        from quickstart_local.chat import search_documents

        mock_retriever = AsyncMock()
        mock_retriever.search.return_value = []

        results = await search_documents("테스트 쿼리", retriever=mock_retriever)

        mock_retriever.search.assert_called_once()
        assert isinstance(results, list)

    def test_build_user_prompt_includes_documents(self):
        """
        사용자 프롬프트에 검색 문서가 포함되는지 확인

        Given: 질문과 문서 리스트
        When: build_user_prompt() 호출
        Then: 프롬프트에 질문과 문서 내용이 포함됨
        """
        from quickstart_local.chat import build_user_prompt

        documents = [
            {"content": "RAG는 검색 증강 생성입니다."},
            {"content": "하이브리드 검색은 Dense + Sparse 결합입니다."},
        ]

        prompt = build_user_prompt("RAG란?", documents)

        assert "RAG란?" in prompt
        assert "RAG는 검색 증강 생성입니다." in prompt
        assert "하이브리드 검색은 Dense + Sparse 결합입니다." in prompt
        assert "문서 1" in prompt
        assert "문서 2" in prompt

    @pytest.mark.asyncio
    async def test_generate_answer_returns_none_without_api_key(self):
        """
        API 키 미설정 시 None 반환 확인

        Given: GOOGLE_API_KEY 미설정
        When: generate_answer() 호출
        Then: None 반환
        """
        from quickstart_local.chat import generate_answer

        with patch.dict("os.environ", {}, clear=True):
            result = await generate_answer("테스트", [{"content": "문서"}])

        assert result is None

    def test_check_llm_available(self):
        """
        LLM 가용성 확인 함수 테스트

        Given: GOOGLE_API_KEY 환경변수 설정/미설정
        When: _check_llm_available() 호출
        Then: 설정 여부에 따라 True/False 반환
        """
        from quickstart_local.chat import _check_llm_available

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            assert _check_llm_available() is True

        with patch.dict("os.environ", {}, clear=True):
            assert _check_llm_available() is False
