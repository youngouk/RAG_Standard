"""
LLM 기반 답변 품질 평가 모듈

LLM을 활용하여 생성된 답변의 품질을 4가지 차원에서 객관적으로 평가합니다.
Self-RAG 시스템에서 답변 재생성 여부를 판단하는 데 사용됩니다.

주요 기능:
- Gemini LLM 기반 품질 평가
- 4가지 평가 차원: 관련성, 근거성, 완전성, 확신도
- 품질 임계값 기반 재생성 필요 여부 판단
"""

import json
from dataclasses import dataclass
from typing import Any

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI

logger = structlog.get_logger(__name__)


@dataclass
class QualityScore:
    """품질 평가 점수"""

    relevance: float  # 관련성 (0.0-1.0)
    grounding: float  # 근거성 (0.0-1.0)
    completeness: float  # 완전성 (0.0-1.0)
    confidence: float  # 확신도 (0.0-1.0)
    overall: float  # 종합 점수 (0.0-1.0)
    reasoning: str  # 평가 근거
    raw_response: dict  # LLM 원본 응답


class LLMQualityEvaluator:
    """
    LLM 기반 답변 품질 평가기

    Gemini LLM을 사용하여 생성된 답변의 품질을 객관적으로 평가합니다.
    Self-RAG 시스템에서 저품질 답변 재생성 여부를 결정하는 핵심 컴포넌트입니다.
    """

    def __init__(
        self,
        llm_provider: str = "google",
        model_name: str = "gemini-2.0-flash-exp",
        api_key: str | None = None,
        quality_threshold: float = 0.75,
        relevance_weight: float = 0.35,
        grounding_weight: float = 0.30,
        completeness_weight: float = 0.25,
        confidence_weight: float = 0.10,
    ):
        self.quality_threshold = quality_threshold
        self.relevance_weight = relevance_weight
        self.grounding_weight = grounding_weight
        self.completeness_weight = completeness_weight
        self.confidence_weight = confidence_weight
        self.llm = None  # Graceful degradation: LLM 초기화 실패 시 None

        # LLM 초기화 (Graceful Degradation - MVP Phase 1)
        if llm_provider == "google":
            # API 키가 없으면 Self-RAG 비활성화
            if not api_key:
                logger.warning(
                    "self_rag_disabled",
                    reason="Google API 키가 제공되지 않았습니다. MVP Phase 1에서는 Self-RAG 없이 진행합니다.",
                )
                return

            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=api_key,  # type: ignore[call-arg]
                    temperature=0.0,  # 일관된 평가를 위해 0
                )
                logger.info(
                    "evaluator_initialized",
                    provider=llm_provider,
                    model=model_name,
                    threshold=quality_threshold,
                )
            except Exception as e:
                # Google 자격증명 오류 또는 기타 초기화 실패
                logger.warning(
                    "evaluator_initialization_failed",
                    provider=llm_provider,
                    error=str(e),
                    reason="Self-RAG 평가기 초기화 실패. MVP Phase 1에서는 Self-RAG 없이 진행합니다.",
                )
                # self.llm은 None 상태로 유지
        else:
            logger.error("unsupported_llm_provider", provider=llm_provider)
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    async def evaluate(self, query: str, answer: str, context: list[str]) -> QualityScore:
        """
        답변 품질 평가

        Args:
            query: 사용자 질문
            answer: 생성된 답변
            context: 검색된 문서 리스트

        Returns:
            QualityScore: 품질 평가 결과
        """
        # Self-RAG 비활성화 상태 확인 (Graceful Degradation)
        if self.llm is None:
            logger.debug("self_rag_disabled_skip_evaluation")
            # MVP Phase 1: Self-RAG 없이 기본 점수 반환
            return self._default_quality_score()

        # 평가 프롬프트 생성
        prompt = self._build_evaluation_prompt(query, answer, context)

        # LLM 평가 수행
        try:
            response = await self.llm.ainvoke(prompt)
            # response.content는 str | list 타입이므로 str 변환
            content: str = (
                response.content if isinstance(response.content, str) else str(response.content)
            )
            raw_response = self._parse_llm_response(content)

            # 점수 추출
            relevance = raw_response.get("relevance", 0.5)
            grounding = raw_response.get("grounding", 0.5)
            completeness = raw_response.get("completeness", 0.5)
            confidence = raw_response.get("confidence", 0.5)
            reasoning = raw_response.get("reasoning", "")

            # 종합 점수 계산
            overall = (
                relevance * self.relevance_weight
                + grounding * self.grounding_weight
                + completeness * self.completeness_weight
                + confidence * self.confidence_weight
            )

            quality_score = QualityScore(
                relevance=relevance,
                grounding=grounding,
                completeness=completeness,
                confidence=confidence,
                overall=overall,
                reasoning=reasoning,
                raw_response=raw_response,
            )

            logger.info(
                "answer_evaluated",
                overall_score=overall,
                relevance=relevance,
                grounding=grounding,
                completeness=completeness,
                confidence=confidence,
                requires_regeneration=overall < self.quality_threshold,
            )

            return quality_score

        except Exception as e:
            logger.error("evaluation_failed", error=str(e))
            # 평가 실패 시 중립 점수 반환
            return self._default_quality_score()

    def requires_regeneration(self, quality: QualityScore) -> bool:
        """재생성 필요 여부 판단"""
        return quality.overall < self.quality_threshold

    def _build_evaluation_prompt(self, query: str, answer: str, context: list[str]) -> str:
        """평가 프롬프트 생성"""
        context_text = "\n\n".join([f"문서 {i+1}:\n{doc}" for i, doc in enumerate(context)])

        return f"""당신은 AI 답변의 품질을 객관적으로 평가하는 전문가입니다.

다음 기준으로 답변을 JSON 형식으로 평가하세요:

📋 평가 기준:
1. relevance (관련성): 질문과 답변이 얼마나 관련이 있는가?
   - 1.0: 질문에 직접적으로 답변함
   - 0.5: 부분적으로 관련 있음
   - 0.0: 질문과 무관함

2. grounding (근거성): 답변이 제공된 컨텍스트에 근거하고 있는가?
   - 1.0: 모든 정보가 컨텍스트에서 나옴
   - 0.5: 일부 추측이 포함됨
   - 0.0: 컨텍스트와 무관한 답변

3. completeness (완전성): 질문에 완전히 답변했는가?
   - 1.0: 질문의 모든 부분에 답변함
   - 0.5: 일부만 답변함
   - 0.0: 답변이 불완전함

4. confidence (확신도): 답변의 확실성 수준은?
   - 1.0: 매우 확실한 답변
   - 0.5: 불확실성 포함
   - 0.0: 매우 불확실함

---

질문:
{query}

제공된 컨텍스트:
{context_text}

생성된 답변:
{answer}

---

다음 JSON 형식으로 응답하세요:
{{
    "relevance": 0.0-1.0,
    "grounding": 0.0-1.0,
    "completeness": 0.0-1.0,
    "confidence": 0.0-1.0,
    "reasoning": "각 점수에 대한 간단한 근거"
}}"""

    def _parse_llm_response(self, content: str) -> dict:
        """LLM 응답 파싱"""
        try:
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            result: dict[str, Any] = json.loads(content)
            return result
        except Exception as e:
            logger.warning("llm_response_parse_failed", error=str(e), content=content[:200])
            return {
                "relevance": 0.5,
                "grounding": 0.5,
                "completeness": 0.5,
                "confidence": 0.5,
                "reasoning": "평가 파싱 실패",
            }

    def _default_quality_score(self) -> QualityScore:
        """기본 품질 점수 (평가 실패 시)"""
        return QualityScore(
            relevance=0.5,
            grounding=0.5,
            completeness=0.5,
            confidence=0.5,
            overall=0.5,
            reasoning="평가 실패로 인한 기본 점수",
            raw_response={},
        )
