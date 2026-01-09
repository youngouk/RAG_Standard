"""
Generation Module - 답변 생성 모듈

Multi-LLM 지원 답변 생성 시스템
- Google Gemini 2.5 Pro
- OpenAI GPT-5
- Anthropic Claude 4.5

자동 failover 및 비용 최적화 지원

사용 예시:
    from app.modules.core.generation import GenerationModule

    generator = GenerationModule(config)
    await generator.initialize()

    result = await generator.generate_answer(
        query="질문",
        context_documents=[doc1, doc2],
        session_id="session-123"
    )

    print(result.answer)
    print(f"사용 모델: {result.model_used}")
    print(f"토큰 사용: {result.tokens_used}")
"""

# 핵심 클래스
from .generator import GenerationModule, GenerationResult

# 프롬프트 관리자
from .prompt_manager import PromptManager, get_prompt_manager

__all__ = [
    # Generation
    "GenerationModule",
    "GenerationResult",
    # Prompt Management
    "PromptManager",
    "get_prompt_manager",
]
