"""
EvaluatorFactory - 설정 기반 평가기 자동 선택 팩토리

YAML 설정에 따라 적절한 평가기 인스턴스를 생성합니다.
기존 GraphRAGFactory, CacheFactory 패턴과 동일한 구조.

사용 예시:
    from app.modules.core.evaluation import EvaluatorFactory

    # YAML 설정 기반 평가기 생성
    evaluator = EvaluatorFactory.create(config, llm_client=llm)

    # 지원 평가기 조회
    EvaluatorFactory.get_supported_evaluators()

지원 평가기:
    - internal: LLM 기반 실시간 내부 평가 (빠름, 저비용, 기본값)
    - ragas: Ragas 라이브러리 기반 배치 평가 (공신력, Phase 2 예정)

의존성:
    - app.lib.logger (로깅)
    - app.modules.core.evaluation.interfaces (IEvaluator Protocol)
    - app.modules.core.evaluation.internal_evaluator (InternalEvaluator)
"""
from typing import Any

from app.lib.logger import get_logger

from .interfaces import IEvaluator
from .internal_evaluator import InternalEvaluator
from .ragas_evaluator import RagasEvaluator

logger = get_logger(__name__)


# 지원 평가기 레지스트리
SUPPORTED_EVALUATORS: dict[str, dict[str, Any]] = {
    # 실시간 내부 평가 (빠름, 저비용, 기본값)
    "internal": {
        "type": "realtime",
        "class": "InternalEvaluator",
        "description": "LLM 기반 실시간 내부 평가 (빠름, 저비용)",
        "default_config": {
            "model": "google/gemini-2.5-flash-lite",
            "timeout": 10.0,
        },
    },
    # 배치 평가 (Ragas 라이브러리 기반)
    "ragas": {
        "type": "batch",
        "class": "RagasEvaluator",
        "description": "Ragas 라이브러리 기반 배치 평가 (공신력)",
        "requires_package": "ragas",
        "metrics": ["faithfulness", "answer_relevancy", "context_precision"],
        "default_config": {
            "metrics": ["faithfulness", "answer_relevancy"],
            "batch_size": 10,
            "llm_model": "gpt-4o",
            "embedding_model": "text-embedding-3-large",
        },
    },
}


class EvaluatorFactory:
    """
    설정 기반 평가기 팩토리

    YAML 설정 파일의 evaluation 섹션을 읽어 적절한 평가기를 생성합니다.

    설정 예시 (features/evaluation.yaml):
        evaluation:
          enabled: false  # 기본 비활성화
          provider: "internal"  # internal, ragas
          internal:
            model: "google/gemini-2.5-flash-lite"
            timeout: 10.0
          ragas:
            metrics: ["faithfulness", "answer_relevancy"]
    """

    @staticmethod
    def create(
        config: dict[str, Any],
        llm_client: Any | None = None,
    ) -> IEvaluator | None:
        """
        설정 기반 평가기 인스턴스 생성

        Args:
            config: 전체 설정 딕셔너리 (evaluation 섹션 포함)
            llm_client: LLM 클라이언트 (internal 평가기에 필요)

        Returns:
            IEvaluator 인터페이스를 구현한 평가기 인스턴스
            비활성화 시 None

        Raises:
            ValueError: 지원하지 않는 프로바이더인 경우
            NotImplementedError: 미구현 프로바이더인 경우
        """
        eval_config = config.get("evaluation", {})

        # 비활성화 체크 (기본값: False)
        if not eval_config.get("enabled", False):
            logger.info("ℹ️  Evaluation disabled via config")
            return None

        provider = eval_config.get("provider", "internal")

        logger.info(f"🔄 EvaluatorFactory: provider={provider}")

        # 지원 여부 확인
        if provider not in SUPPORTED_EVALUATORS:
            supported = list(SUPPORTED_EVALUATORS.keys())
            raise ValueError(
                f"지원하지 않는 평가기 프로바이더: {provider}. "
                f"지원 목록: {supported}"
            )

        # 프로바이더별 평가기 생성
        if provider == "internal":
            return EvaluatorFactory._create_internal_evaluator(
                config, eval_config, llm_client
            )
        elif provider == "ragas":
            return EvaluatorFactory._create_ragas_evaluator(config, eval_config)
        else:
            raise ValueError(f"지원하지 않는 평가기 프로바이더: {provider}")

    @staticmethod
    def _create_internal_evaluator(
        config: dict[str, Any],
        eval_config: dict[str, Any],
        llm_client: Any | None,
    ) -> InternalEvaluator:
        """
        Internal 평가기 생성

        Args:
            config: 전체 설정
            eval_config: evaluation 섹션 설정
            llm_client: LLM 클라이언트

        Returns:
            InternalEvaluator 인스턴스
        """
        internal_config = eval_config.get("internal", {})
        defaults = SUPPORTED_EVALUATORS["internal"]["default_config"]

        evaluator = InternalEvaluator(
            llm_client=llm_client,
            model=internal_config.get("model", defaults["model"]),
            timeout=internal_config.get("timeout", defaults["timeout"]),
        )

        logger.info(
            f"✅ InternalEvaluator 생성: "
            f"model={internal_config.get('model', defaults['model'])}"
        )
        return evaluator

    @staticmethod
    def _create_ragas_evaluator(
        config: dict[str, Any],
        eval_config: dict[str, Any],
    ) -> IEvaluator:
        """
        Ragas 평가기 생성

        Args:
            config: 전체 설정
            eval_config: evaluation 섹션 설정

        Returns:
            RagasEvaluator 인스턴스
        """
        ragas_config = eval_config.get("ragas", {})
        defaults = SUPPORTED_EVALUATORS["ragas"]["default_config"]

        evaluator = RagasEvaluator(
            metrics=ragas_config.get("metrics", defaults["metrics"]),
            batch_size=ragas_config.get("batch_size", defaults["batch_size"]),
            llm_model=ragas_config.get("llm_model", defaults["llm_model"]),
            embedding_model=ragas_config.get(
                "embedding_model", defaults["embedding_model"]
            ),
        )

        logger.info(
            f"✅ RagasEvaluator 생성: "
            f"metrics={ragas_config.get('metrics', defaults['metrics'])}, "
            f"available={evaluator.is_available()}"
        )
        return evaluator

    @staticmethod
    def get_supported_evaluators() -> list[str]:
        """
        지원하는 모든 평가기 이름 반환

        Returns:
            평가기 이름 리스트
        """
        return list(SUPPORTED_EVALUATORS.keys())

    @staticmethod
    def get_evaluator_info(name: str) -> dict[str, Any] | None:
        """
        특정 평가기의 상세 정보 반환

        Args:
            name: 평가기 이름

        Returns:
            평가기 정보 딕셔너리 또는 None
        """
        return SUPPORTED_EVALUATORS.get(name)

    @staticmethod
    def list_evaluators_by_type(eval_type: str) -> list[str]:
        """
        타입별 평가기 목록 반환

        Args:
            eval_type: 평가기 타입 (realtime, batch 등)

        Returns:
            해당 타입의 평가기 이름 리스트
        """
        return [
            name
            for name, info in SUPPORTED_EVALUATORS.items()
            if info["type"] == eval_type
        ]
