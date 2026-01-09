"""
RRF 점수 정규화 유틸리티
========================================
기능: RRF(Reciprocal Rank Fusion) 점수를 0~100점 범위로 변환
참조: docs/prd/PRD_Phase2.md - "검색 점수 표시(정규화)"

RRF 점수 특성:
- 공식: score = weight / (rrf_k + rank)
- rrf_k = 60 (표준값)
- 단일 쿼리 최대값: 1/(60+1) ≈ 0.0164
- Multi-Query(3개, 가중치 합 2.4) 최대값: ≈ 0.0393

정규화 방식:
- 이론적 최대값 기준으로 100점 정규화
- 최대값 = weight_sum / (rrf_k + 1)
"""

from dataclasses import dataclass

from app.lib.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoreNormalizationConfig:
    """점수 정규화 설정"""

    enabled: bool = True
    rrf_k: int = 60  # RRF 상수 (orchestrator.py와 동일)
    default_weight_sum: float = 3.0  # 기본 가중치 합 (query_weights 합)
    min_score: float = 0.0  # 출력 최소값
    max_score: float = 100.0  # 출력 최대값
    decimal_places: int = 1  # 소수점 자릿수


class RRFScoreNormalizer:
    """
    RRF 점수 정규화 클래스

    사용 예시:
        normalizer = RRFScoreNormalizer()
        normalized = normalizer.normalize(0.0283)  # → 72.0
        normalized = normalizer.normalize(0.0283, weight_sum=2.4)  # → 71.9

        # 배치 정규화
        scores = [0.0283, 0.0147, 0.0100]
        normalized_scores = normalizer.normalize_batch(scores)
    """

    def __init__(self, config: ScoreNormalizationConfig | None = None):
        """
        초기화

        Args:
            config: 정규화 설정 (None이면 기본값 사용)
        """
        self.config = config or ScoreNormalizationConfig()
        self._log_config()

    def _log_config(self) -> None:
        """설정 로깅"""
        if self.config.enabled:
            max_theoretical = self._calculate_max_score(self.config.default_weight_sum)
            logger.debug(
                f"📊 RRF 점수 정규화 활성화: "
                f"rrf_k={self.config.rrf_k}, "
                f"weight_sum={self.config.default_weight_sum}, "
                f"이론적 최대값={max_theoretical:.4f}"
            )

    def _calculate_max_score(self, weight_sum: float) -> float:
        """
        이론적 RRF 최대 점수 계산

        모든 쿼리에서 동일 문서가 1위일 때의 점수:
        max_score = weight_sum / (rrf_k + 1)

        Args:
            weight_sum: 쿼리 가중치 합

        Returns:
            이론적 최대 RRF 점수
        """
        return weight_sum / (self.config.rrf_k + 1)

    def normalize(
        self,
        rrf_score: float,
        weight_sum: float | None = None,
    ) -> float:
        """
        RRF 점수를 0~100 범위로 정규화

        정규화 공식:
            normalized = (rrf_score / max_theoretical) * 100

        Args:
            rrf_score: 원본 RRF 점수 (일반적으로 0.01 ~ 0.04 범위)
            weight_sum: 쿼리 가중치 합 (None이면 기본값 사용)

        Returns:
            정규화된 점수 (0 ~ 100 범위)
        """
        # 정규화 비활성화 시 원본 반환
        if not self.config.enabled:
            return rrf_score

        # 유효성 검사
        if rrf_score < 0:
            logger.warning(f"⚠️ 음수 RRF 점수: {rrf_score}")
            return self.config.min_score

        # 가중치 합 결정
        effective_weight_sum = weight_sum or self.config.default_weight_sum

        # 이론적 최대값 계산
        max_theoretical = self._calculate_max_score(effective_weight_sum)

        # 정규화
        if max_theoretical <= 0:
            logger.warning(f"⚠️ 최대값이 0 이하: {max_theoretical}")
            return self.config.min_score

        normalized = (rrf_score / max_theoretical) * self.config.max_score

        # 범위 클램핑 및 반올림
        normalized = max(self.config.min_score, min(self.config.max_score, normalized))
        normalized = round(normalized, self.config.decimal_places)

        return normalized

    def normalize_batch(
        self,
        rrf_scores: list[float],
        weight_sum: float | None = None,
    ) -> list[float]:
        """
        여러 RRF 점수를 일괄 정규화

        Args:
            rrf_scores: RRF 점수 리스트
            weight_sum: 쿼리 가중치 합

        Returns:
            정규화된 점수 리스트
        """
        return [self.normalize(score, weight_sum) for score in rrf_scores]

    @classmethod
    def from_config(cls, config_dict: dict) -> "RRFScoreNormalizer":
        """
        딕셔너리 설정에서 인스턴스 생성

        Args:
            config_dict: 설정 딕셔너리 (rag.yaml의 score_normalization 섹션)

        Returns:
            RRFScoreNormalizer 인스턴스

        사용 예시:
            config = {
                "enabled": True,
                "rrf_k": 60,
                "default_weight_sum": 3.0,
                "min_score": 0,
                "max_score": 100,
                "decimal_places": 1
            }
            normalizer = RRFScoreNormalizer.from_config(config)
        """
        normalization_config = ScoreNormalizationConfig(
            enabled=config_dict.get("enabled", True),
            rrf_k=config_dict.get("rrf_k", 60),
            default_weight_sum=config_dict.get("default_weight_sum", 3.0),
            min_score=config_dict.get("min_score", 0.0),
            max_score=config_dict.get("max_score", 100.0),
            decimal_places=config_dict.get("decimal_places", 1),
        )
        return cls(config=normalization_config)


# 기본 인스턴스 (편의용)
_default_normalizer: RRFScoreNormalizer | None = None


def get_default_normalizer() -> RRFScoreNormalizer:
    """기본 정규화 인스턴스 반환 (싱글톤)"""
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = RRFScoreNormalizer()
    return _default_normalizer


def normalize_rrf_score(
    rrf_score: float,
    weight_sum: float | None = None,
) -> float:
    """
    RRF 점수 정규화 편의 함수

    Args:
        rrf_score: 원본 RRF 점수
        weight_sum: 쿼리 가중치 합 (선택)

    Returns:
        정규화된 점수 (0~100)

    사용 예시:
        >>> normalize_rrf_score(0.0283)
        72.0
        >>> normalize_rrf_score(0.0147)
        37.4
    """
    return get_default_normalizer().normalize(rrf_score, weight_sum)
