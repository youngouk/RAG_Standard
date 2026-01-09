"""
GPT-5-nano 기반 지능형 쿼리 확장 엔진

Phase 1.4: 레거시 의존성 완전 제거
Phase 2.0: OpenAI 직접 호출 제거, llm_factory 필수화

- LLM Factory를 통한 Multi-LLM fallback 지원
- 레거시 OpenAI 직접 호출 코드 제거
- IQueryExpansionEngine 인터페이스 준수
"""

import asyncio
import json
import re
from typing import Any, TypedDict, cast

import structlog
from cachetools import TTLCache

from app.lib.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerFactory,
)

from .interface import (
    ExpandedQuery,
    IQueryExpansionEngine,
    QueryComplexity,
    SearchIntent,
)

logger = structlog.get_logger(__name__)


class Stats(TypedDict):
    """GPT5QueryExpansionEngine 성능 통계 타입"""

    total_expansions: int
    successful_expansions: int
    cache_hits: int
    cache_misses: int
    average_response_time: float
    complexity_distribution: dict[str, int]
    intent_distribution: dict[str, int]
    gpt5_api_calls: int
    json_parse_failures: int


class GPT5QueryExpansionEngine(IQueryExpansionEngine):
    """
    GPT-5-nano 기반 Query Expansion Engine

    **Phase 1.4 리팩토링**: 레거시 의존성 완전 제거
    - 기존 documents/query_expansion.py의 검증된 로직 재활용
    - GPT-5-nano API 호출, 3단계 JSON 파싱, TTL 캐싱 포함
    - IQueryExpansionEngine 인터페이스 준수

    Features:
    - GPT-5-nano 기반 다중 쿼리 생성 (기본 5개)
    - TTLCache (1000개, 86400초 = 1일)
    - 3단계 JSON 파싱 (정상 → 코드블록 → 수동 추출)
    - 복잡도 및 의도 자동 분석
    - Circuit Breaker 보호
    - LLM Factory 지원 (Multi-LLM fallback)
    """

    def __init__(
        self,
        api_key: str = "",  # 레거시 호환, 사용되지 않음
        num_expansions: int = 5,
        max_tokens: int = 500,
        temperature: float = 0.7,
        cache_size: int = 1000,
        cache_ttl: int = 86400,  # 1일
        llm_factory: Any = None,  # 필수 (None이면 에러)
        provider: str = "google",  # LLM Factory의 선호 제공자 (google = Gemini Flash)
        circuit_breaker_factory: CircuitBreakerFactory | None = None,
    ):
        """
        Args:
            api_key: (Deprecated) 사용되지 않음, 하위 호환성 유지용
            num_expansions: 생성할 확장 쿼리 수
            max_tokens: LLM 응답 최대 토큰
            temperature: 생성 온도 (0.0-1.0)
            cache_size: 캐시 최대 크기
            cache_ttl: 캐시 유효 시간 (초)
            llm_factory: LLM Factory 인스턴스 (필수)
            provider: LLM Factory의 선호 제공자 (google, openai, anthropic)
            circuit_breaker_factory: DI Container의 CircuitBreaker 팩토리

        Raises:
            ValueError: llm_factory가 None인 경우
        """
        # llm_factory 필수 검증
        if llm_factory is None:
            raise ValueError(
                "llm_factory는 필수입니다. "
                "DI Container의 AppContainer.llm_factory()를 사용하세요."
            )

        self.num_expansions = num_expansions
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.llm_factory = llm_factory
        self.provider = provider  # 선호 제공자 저장
        self.circuit_breaker_factory = circuit_breaker_factory

        # TTL 캐시 초기화
        self.expansion_cache: TTLCache[str, ExpandedQuery] = TTLCache(
            maxsize=cache_size, ttl=cache_ttl
        )
        logger.info(
            "쿼리 확장 캐시 초기화",
            maxsize=cache_size,
            ttl_seconds=cache_ttl,
        )

        # 성능 통계
        self.stats: Stats = {
            "total_expansions": 0,
            "successful_expansions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_response_time": 0.0,
            "complexity_distribution": {c.value: 0 for c in QueryComplexity},
            "intent_distribution": {i.value: 0 for i in SearchIntent},
            "gpt5_api_calls": 0,
            "json_parse_failures": 0,
        }

        # GPT-5-nano용 최적화된 프롬프트
        self.expansion_prompt = self._create_expansion_prompt()

    def _create_expansion_prompt(self) -> str:
        """GPT-5-nano용 최적화된 쿼리 확장 프롬프트"""
        return """당신은 한국어 문서 검색을 위한 쿼리 확장 전문가입니다.

주어진 사용자 쿼리를 분석하고 검색 효율성을 극대화하기 위해 확장해주세요.

**분석 요구사항:**
1. 동의어 및 유사어 발굴 (한국어 특성 고려)
2. 핵심 키워드 추출 및 중요도 가중치 부여 (0.1-1.0)
3. 검색 의도 분류 (factual/procedural/conceptual/comparative/problem_solving)
4. 쿼리 복잡도 평가 (simple/medium/complex/contextual)
5. 다양한 관점의 확장 쿼리 생성 (각 쿼리별 가중치 포함)

**응답 형식:** 순수 JSON만 반환하세요. 마크다운 코드 블록(```)을 사용하지 마세요.

{{
  "original_query": "원본 쿼리",
  "synonyms": ["동의어1", "동의어2", "동의어3"],
  "related_terms": ["관련용어1", "관련용어2", "관련용어3"],
  "core_keywords": [
    {{"keyword": "핵심키워드1", "weight": 0.9}},
    {{"keyword": "핵심키워드2", "weight": 0.7}},
    {{"keyword": "핵심키워드3", "weight": 0.5}}
  ],
  "intent": "factual",
  "complexity": "medium",
  "expanded_queries": [
    {{"query": "확장쿼리1", "weight": 1.0, "focus": "주요_관점"}},
    {{"query": "확장쿼리2", "weight": 0.8, "focus": "보조_관점"}},
    {{"query": "확장쿼리3", "weight": 0.6, "focus": "세부_관점"}}
  ],
  "search_strategy": "hybrid"
}}

**사용자 쿼리:** {query}

**중요:**
- 순수 JSON만 반환 (코드 블록 ``` 금지)
- intent 값: factual, procedural, conceptual, comparative, problem_solving 중 하나
- complexity 값: simple, medium, complex, contextual 중 하나
- search_strategy 값: broad, focused, hybrid, contextual 중 하나
- weight는 0.1-1.0 범위의 실수
- 검색 효율성에 집중"""

    async def expand_query(
        self, query: str, context: list[dict] | None = None
    ) -> ExpandedQuery | None:
        """
        쿼리 확장 메인 메서드 (캐싱 적용)

        Args:
            query: 원본 사용자 쿼리
            context: 대화 컨텍스트 (선택적, 향후 컨텍스트 기반 확장에 사용 가능)

        Returns:
            ExpandedQuery 객체 또는 None (실패시)
        """
        start_time = asyncio.get_event_loop().time()
        self.stats["total_expansions"] += 1

        # 캐시 키 생성 (쿼리 정규화)
        cache_key = query.strip().lower()

        # 캐시 확인
        if cache_key in self.expansion_cache:
            self.stats["cache_hits"] += 1
            cached_result = self.expansion_cache[cache_key]
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(
                "✅ 캐시 히트!",
                query=query[:50],
                elapsed_ms=f"{elapsed*1000:.1f}",
                cache_hit_rate=f"{self.stats['cache_hits']/self.stats['total_expansions']*100:.1f}%",
            )
            return cached_result

        # 캐시 미스
        self.stats["cache_misses"] += 1
        logger.debug("❌ 캐시 미스, 쿼리 확장 검토 시작", query=query[:50])

        try:
            # 1. 사전 필터링 - 간단한 쿼리는 빠른 처리
            if self._is_simple_query(query):
                logger.info("✅ 단순 쿼리로 판단, GPT-5-nano 호출 생략", query=query[:50])
                result = self._create_simple_expansion(query)
                self.expansion_cache[cache_key] = result
                return result

            # 2. GPT-5-nano 호출
            logger.info("🔄 복잡한 쿼리로 판단, GPT-5-nano 호출 시작", query=query[:50])
            logger.debug("GPT-5-nano 쿼리 확장 시작", query=query)
            expanded_data = await self._call_gpt5_nano(query)

            if not expanded_data:
                logger.warning("GPT-5 확장 실패, 폴백 사용", query=query)
                return self._create_fallback_expansion(query)

            # 3. 구조화된 객체 생성
            expanded_query = self._parse_expansion_result(expanded_data, query)

            # 4. 통계 업데이트
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_stats(expanded_query, processing_time)

            # 5. 캐시에 저장
            self.expansion_cache[cache_key] = expanded_query

            logger.info(
                "쿼리 확장 완료 (캐시 저장)",
                expanded_count=len(expanded_query.expansions),
                intent=expanded_query.intent.value,
                complexity=expanded_query.complexity.value,
                processing_time_ms=f"{processing_time*1000:.1f}",
            )

            return expanded_query

        except Exception as e:
            logger.error("쿼리 확장 오류", error=str(e))
            # 폴백 결과도 캐싱 (실패 반복 방지)
            fallback_result = self._create_fallback_expansion(query)
            self.expansion_cache[cache_key] = fallback_result
            return fallback_result

    def _is_simple_query(self, query: str) -> bool:
        """간단한 쿼리 판별 로직"""
        # 짧은 키워드성 쿼리
        if len(query.strip()) < 10:
            return True

        # 단순 명사구
        simple_patterns = [
            lambda q: len(q.split()) <= 2,  # 2단어 이하
            lambda q: not any(char in q for char in "?!"),  # 질문/감탄문 아님
            lambda q: not any(word in q for word in ["어떻게", "왜", "무엇", "언제", "어디서"]),
        ]

        return sum(pattern(query) for pattern in simple_patterns) >= 2

    async def _call_gpt5_nano(self, query: str) -> dict[str, Any] | None:
        """GPT-5-nano API 호출 (강화된 JSON 파싱)"""
        try:
            self.stats["gpt5_api_calls"] += 1

            # GPT-5 새로운 API를 위한 input 텍스트 준비
            input_text = f"""System: You are a Korean query expansion specialist. Always respond in valid JSON format.

User: {self.expansion_prompt.format(query=query)}"""

            # Circuit Breaker 설정
            cb_config = CircuitBreakerConfig(
                failure_threshold=3, timeout=15.0, error_rate_threshold=0.3
            )
            if self.circuit_breaker_factory:
                breaker = self.circuit_breaker_factory.get("query_expansion", cb_config)
            else:
                # circuit_breaker_factory가 없으면 breaker 없이 직접 호출
                breaker = None

            # LLM Factory 사용 (Multi-LLM fallback)
            if breaker:
                content, provider = await breaker.call(
                    self.llm_factory.generate_with_fallback,
                    prompt=input_text,
                    system_prompt=None,
                    preferred_provider=self.provider,
                )
            else:
                # Circuit Breaker 없이 직접 호출
                content, provider = await self.llm_factory.generate_with_fallback(
                    prompt=input_text,
                    system_prompt=None,
                    preferred_provider=self.provider,
                )
            logger.debug(
                "쿼리 확장 응답 (LLM Factory)",
                provider=provider,
                length=len(content),
            )

            # 강화된 JSON 파싱 (3단계 폴백)
            parsed_json = self._parse_json_with_fallback(content)

            if parsed_json:
                return parsed_json
            else:
                self.stats["json_parse_failures"] += 1
                return None

        except Exception as e:
            logger.error("GPT-5-nano API 호출 오류", error=str(e))
            return None

    def _parse_json_with_fallback(self, content: str) -> dict[str, Any] | None:
        """
        3단계 폴백 JSON 파싱

        1단계: 정상 JSON 파싱
        2단계: 코드 블록 추출 후 파싱
        3단계: 수동 필드 추출 파싱
        """
        # === 1단계: 정상 JSON 파싱 시도 ===
        try:
            return cast(dict[str, Any], json.loads(content))
        except json.JSONDecodeError as e1:
            logger.debug("1단계 파싱 실패", error=str(e1))

        # === 2단계: JSON 코드 블록 추출 시도 ===
        try:
            # ```json ... ``` 블록 추출
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                extracted_json = json_match.group(1)
                logger.debug("JSON 코드 블록 추출 성공")
                return cast(dict[str, Any], json.loads(extracted_json))

            # ``` ... ``` 일반 코드 블록 추출 (json 키워드 없이)
            json_match = re.search(r"```\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                extracted_json = json_match.group(1)
                logger.debug("일반 코드 블록 추출 성공")
                return cast(dict[str, Any], json.loads(extracted_json))

            # 코드 블록 없이 { ... } 추출
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                extracted_json = json_match.group(0)
                logger.debug("중괄호 블록 추출 성공")
                return cast(dict[str, Any], json.loads(extracted_json))

        except json.JSONDecodeError as e2:
            logger.debug("2단계 파싱 실패", error=str(e2))
        except Exception as e2:
            logger.warning("2단계 추출 오류", error=str(e2))

        # === 3단계: 수동 필드 추출 폴백 ===
        logger.warning("3단계 수동 파싱 시도", content_preview=content[:200])
        try:
            return self._manual_parse_json_fields(content)
        except Exception as e3:
            logger.error("3단계 수동 파싱 실패", error=str(e3))
            logger.error("파싱 실패한 전체 응답", content=content)
            return None

    def _manual_parse_json_fields(self, content: str) -> dict[str, Any]:
        """
        수동 JSON 필드 추출 (최종 폴백)

        불완전한 JSON에서 최소 필수 필드만 추출
        """
        result: dict[str, Any] = {
            "original_query": "",
            "synonyms": [],
            "related_terms": [],
            "core_keywords": [],
            "intent": "factual",
            "complexity": "medium",
            "expanded_queries": [],
            "search_strategy": "hybrid",
        }

        # 정규식으로 필드 추출 시도
        try:
            # original_query 추출
            query_match = re.search(r'"original_query"\s*:\s*"([^"]*)"', content)
            if query_match:
                result["original_query"] = query_match.group(1)

            # synonyms 배열 추출
            synonyms_match = re.search(r'"synonyms"\s*:\s*\[(.*?)\]', content, re.DOTALL)
            if synonyms_match:
                synonyms_str = synonyms_match.group(1)
                result["synonyms"] = [
                    s.strip().strip('"') for s in synonyms_str.split(",") if s.strip()
                ]

            # expanded_queries 추출
            exp_queries_match = re.search(r'"expanded_queries"\s*:\s*\[(.*?)\]', content, re.DOTALL)
            if exp_queries_match:
                exp_str = exp_queries_match.group(1)
                # 간단한 query 필드만 추출
                query_matches = re.findall(r'"query"\s*:\s*"([^"]*)"', exp_str)
                result["expanded_queries"] = [
                    {"query": q, "weight": 0.8, "focus": "extracted"} for q in query_matches
                ]

            logger.info(
                "수동 파싱 성공",
                expanded_queries_count=len(result["expanded_queries"]),
            )
            return result

        except Exception as e:
            logger.error("수동 필드 추출 실패", error=str(e))
            raise

    def _parse_expansion_result(
        self, raw_data: dict[str, Any], original_query: str
    ) -> ExpandedQuery:
        """GPT-5 응답을 구조화된 객체로 변환 (신규 인터페이스 스펙)"""
        try:
            # expanded_queries에서 query 문자열만 추출
            expanded_queries_raw = raw_data.get("expanded_queries", [])
            expansions = []
            if isinstance(expanded_queries_raw, list):
                for item in expanded_queries_raw:
                    if isinstance(item, dict) and "query" in item:
                        expansions.append(item["query"])
                    elif isinstance(item, str):
                        expansions.append(item)

            # 확장 쿼리가 없으면 원본 쿼리 사용
            if not expansions:
                expansions = [original_query]

            return ExpandedQuery(
                original=original_query,
                expansions=expansions,
                complexity=QueryComplexity(raw_data.get("complexity", "medium")),
                intent=SearchIntent(raw_data.get("intent", "factual")),
                metadata={
                    "synonyms": raw_data.get("synonyms", []),
                    "related_terms": raw_data.get("related_terms", []),
                    "core_keywords": raw_data.get("core_keywords", []),
                    "search_strategy": raw_data.get("search_strategy", "hybrid"),
                    "raw_expanded_queries": expanded_queries_raw,
                },
            )
        except (ValueError, KeyError) as e:
            logger.warning("확장 결과 파싱 오류, 폴백 사용", error=str(e))
            return self._create_fallback_expansion(original_query)

    def _create_simple_expansion(self, query: str) -> ExpandedQuery:
        """간단한 쿼리용 빠른 확장 (신규 인터페이스 스펙)"""
        keywords = query.split()

        return ExpandedQuery(
            original=query,
            expansions=[query],
            complexity=QueryComplexity.SIMPLE,
            intent=SearchIntent.FACTUAL,
            metadata={
                "synonyms": [],
                "related_terms": [],
                "core_keywords": [
                    {"keyword": kw, "weight": 1.0 - (i * 0.1)} for i, kw in enumerate(keywords[:3])
                ],
                "search_strategy": "focused",
            },
        )

    def _create_fallback_expansion(self, query: str) -> ExpandedQuery:
        """폴백 확장 (GPT-5 실패시, 신규 인터페이스 스펙)"""
        keywords = query.split()

        # 확장 쿼리: 원본 + 키워드 조합
        expansions = [query]
        if keywords:
            keyword_query = " ".join(keywords)
            if keyword_query != query:
                expansions.append(keyword_query)

        return ExpandedQuery(
            original=query,
            expansions=expansions,
            complexity=QueryComplexity.MEDIUM,
            intent=SearchIntent.FACTUAL,
            metadata={
                "synonyms": [],
                "related_terms": [],
                "core_keywords": [{"keyword": kw, "weight": 0.8} for kw in keywords],
                "search_strategy": "hybrid",
            },
        )

    def _update_stats(self, expanded_query: ExpandedQuery, processing_time: float) -> None:
        """통계 업데이트"""
        self.stats["successful_expansions"] += 1
        self.stats["complexity_distribution"][expanded_query.complexity.value] += 1
        self.stats["intent_distribution"][expanded_query.intent.value] += 1

        # 평균 응답 시간 업데이트
        total_expansions = self.stats["successful_expansions"]
        current_avg = self.stats["average_response_time"]
        self.stats["average_response_time"] = (
            current_avg * (total_expansions - 1) + processing_time
        ) / total_expansions

    def get_stats(self) -> dict[str, Any]:
        """확장 성능 통계"""
        success_rate = (
            self.stats["successful_expansions"] / max(1, self.stats["total_expansions"])
        ) * 100

        return {
            **self.stats,
            "success_rate_percentage": round(success_rate, 2),
            "average_response_time_ms": round(self.stats["average_response_time"] * 1000, 2),
            "cache_size": len(self.expansion_cache),
            "cache_maxsize": self.expansion_cache.maxsize,
            "cache_ttl": self.expansion_cache.ttl,
        }

    # ==================== IQueryExpansionEngine 인터페이스 구현 ====================

    async def expand(self, query: str, num_expansions: int = 5, **kwargs: Any) -> ExpandedQuery:
        """
        인터페이스 메서드: 쿼리 확장

        기존 expand_query() 메서드에 위임하여 중복 구현 방지

        Args:
            query: 확장할 원본 쿼리
            num_expansions: 생성할 확장 쿼리 수 (현재 무시, self.num_expansions 사용)
            **kwargs: 추가 파라미터 (확장성)

        Returns:
            ExpandedQuery 객체
        """
        # 기존 검증된 로직 재사용 (DRY 원칙)
        result = await self.expand_query(query)
        if result is None:
            # 폴백: 기본 확장 반환
            logger.warning("expand() 실패, 폴백 사용", query=query)
            return self._create_fallback_expansion(query)
        return result

    async def analyze_complexity(self, query: str) -> QueryComplexity:
        """
        쿼리 복잡도 분석

        expand_query() 결과에서 복잡도만 추출하여 반환
        캐싱 덕분에 중복 API 호출 없음

        Args:
            query: 분석할 쿼리

        Returns:
            QueryComplexity Enum (SIMPLE, MEDIUM, COMPLEX, CONTEXTUAL)
        """
        try:
            result = await self.expand_query(query)
            if result:
                return result.complexity
            else:
                # 폴백: MEDIUM 반환
                logger.warning("복잡도 분석 실패, MEDIUM 반환", query=query)
                return QueryComplexity.MEDIUM
        except Exception as e:
            logger.error("복잡도 분석 오류", query=query, error=str(e))
            return QueryComplexity.MEDIUM

    async def detect_intent(self, query: str) -> SearchIntent:
        """
        검색 의도 감지

        expand_query() 결과에서 의도만 추출하여 반환
        캐싱 덕분에 중복 API 호출 없음

        Args:
            query: 분석할 쿼리

        Returns:
            SearchIntent Enum (FACTUAL, PROCEDURAL, CONCEPTUAL, COMPARATIVE, PROBLEM_SOLVING)
        """
        try:
            result = await self.expand_query(query)
            if result:
                return result.intent
            else:
                # 폴백: FACTUAL 반환
                logger.warning("의도 감지 실패, FACTUAL 반환", query=query)
                return SearchIntent.FACTUAL
        except Exception as e:
            logger.error("의도 감지 오류", query=query, error=str(e))
            return SearchIntent.FACTUAL

    async def health_check(self) -> bool:
        """
        LLM API 연결 상태 확인

        LLM Factory가 존재하면 정상으로 간주 (팩토리 내부에서 fallback 처리)

        Returns:
            True: LLM 팩토리 정상, False: LLM 팩토리 없음
        """
        # llm_factory는 필수이므로 항상 존재
        # 팩토리가 존재하면 정상으로 간주 (팩토리 내부에서 fallback 처리)
        if self.llm_factory:
            logger.debug("health_check: LLM 팩토리 사용, 정상 간주")
            return True
        return False

    # ==================== 하위 호환성: from_config() 팩토리 메서드 ====================

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        llm_factory: Any = None,  # 필수
        circuit_breaker_factory: CircuitBreakerFactory | None = None,
    ) -> "GPT5QueryExpansionEngine":
        """
        config dict에서 인스턴스 생성

        Args:
            config: 전체 설정 dict (app/config/config.yaml 형식)
            llm_factory: LLM Factory 인스턴스 (필수)
            circuit_breaker_factory: DI Container의 CircuitBreaker 팩토리

        Returns:
            GPT5QueryExpansionEngine 인스턴스

        Raises:
            ValueError: llm_factory가 None인 경우

        Example:
            >>> engine = GPT5QueryExpansionEngine.from_config(config, llm_factory=factory)
        """
        # llm_factory 필수 검증
        if llm_factory is None:
            raise ValueError(
                "llm_factory는 필수입니다. "
                "GPT5QueryExpansionEngine.from_config(config, llm_factory=factory)로 호출하세요."
            )

        # 설정 추출 (query_expansion.yaml 우선 참조)
        query_expansion_config = config.get("query_expansion", {})
        llm_config = query_expansion_config.get("llm", {})
        multi_query_config = query_expansion_config.get(
            "multi_query", config.get("multi_query", {})
        )

        # Provider 설정 읽기 (query_expansion.llm.provider 우선, 없으면 기본값: openai)
        # 설정 파일 구조: query_expansion.llm.provider
        provider = llm_config.get("provider", query_expansion_config.get("provider", "openai"))

        # 생성자 호출
        return cls(
            num_expansions=multi_query_config.get("num_expansions", 5),
            max_tokens=multi_query_config.get("max_tokens", 500),
            temperature=multi_query_config.get("temperature", 0.7),
            cache_size=1000,  # 고정값 (레거시 호환)
            cache_ttl=86400,  # 1일 (레거시 호환)
            llm_factory=llm_factory,
            provider=provider,  # 설정에서 읽은 provider 전달
            circuit_breaker_factory=circuit_breaker_factory,
        )
