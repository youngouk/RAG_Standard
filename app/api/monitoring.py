"""
Monitoring API Endpoints
Circuit Breaker, 비용 추적, 성능 메트릭 모니터링
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..lib.auth import get_api_key
from ..lib.logger import get_logger

# 순환 임포트 방지: 타입 힌트용으로만 임포트
if TYPE_CHECKING:
    from ..core.di_container import AppContainer


def _get_container() -> AppContainer:
    """지연 임포트로 순환 임포트 방지"""
    from ..core.di_container import AppContainer

    return AppContainer()


logger = get_logger(__name__)

# ✅ H1 보안 패치: 라우터 레벨 인증 추가
# Monitoring API는 비용, 성능 정보 등 민감한 데이터 노출
router = APIRouter(tags=["Monitoring"], dependencies=[Depends(get_api_key)])


class MonitoringResponse(BaseModel):
    """모니터링 응답"""

    success: bool
    data: dict[str, Any]
    message: str = ""


@router.get("/monitoring/metrics", response_model=MonitoringResponse)
async def get_metrics():
    """
    성능 메트릭 조회

    Returns:
        함수별 응답 시간 통계 (평균, 최소, 최대, P95, 에러 수)
    """
    try:
        container = _get_container()
        metrics = container.performance_metrics()
        all_stats = metrics.get_all_stats()

        return MonitoringResponse(
            success=True,
            data={"metrics": all_stats},
            message=f"{len(all_stats)}개 함수의 성능 메트릭",
        )
    except Exception as e:
        logger.error(f"메트릭 조회 실패: {e}")
        return MonitoringResponse(success=False, data={}, message=f"메트릭 조회 실패: {str(e)}")


@router.get("/monitoring/costs", response_model=MonitoringResponse)
async def get_costs():
    """
    LLM API 비용 조회

    Returns:
        제공자별 토큰 사용량 및 비용 (USD)
    """
    try:
        container = _get_container()
        cost_tracker = container.cost_tracker()
        summary = cost_tracker.get_summary()

        return MonitoringResponse(
            success=True, data=summary, message=f"총 비용: ${summary['total_cost_usd']}"
        )
    except Exception as e:
        logger.error(f"비용 조회 실패: {e}")
        return MonitoringResponse(success=False, data={}, message=f"비용 조회 실패: {str(e)}")


@router.get("/monitoring/circuit-breakers", response_model=MonitoringResponse)
async def get_circuit_breakers():
    """
    Circuit Breaker 상태 조회

    Returns:
        모든 Circuit Breaker의 상태 (CLOSED, OPEN, HALF_OPEN)
    """
    try:
        container = _get_container()
        cb_factory = container.circuit_breaker_factory()
        all_cbs = cb_factory.get_all_states()

        # 상태별 개수
        state_counts = {"closed": 0, "open": 0, "half_open": 0}

        for cb_data in all_cbs.values():
            state = cb_data["state"]
            if state in state_counts:
                state_counts[state] += 1

        return MonitoringResponse(
            success=True,
            data={
                "circuit_breakers": all_cbs,
                "state_counts": state_counts,
                "total_count": len(all_cbs),
            },
            message=f"총 {len(all_cbs)}개 Circuit Breaker 활성",
        )
    except Exception as e:
        logger.error(f"Circuit Breaker 조회 실패: {e}")
        return MonitoringResponse(
            success=False, data={}, message=f"Circuit Breaker 조회 실패: {str(e)}"
        )


@router.get("/monitoring/health", response_model=MonitoringResponse)
async def health_check():
    """
    종합 헬스 체크

    Returns:
        전체 시스템 건강 상태
    """
    try:
        container = _get_container()

        # Circuit Breaker 상태
        cb_factory = container.circuit_breaker_factory()
        all_cbs = cb_factory.get_all_states()
        open_cbs = [name for name, cb in all_cbs.items() if cb["state"] == "open"]

        # 비용 정보
        cost_tracker = container.cost_tracker()
        cost_summary = cost_tracker.get_summary()

        # 성능 메트릭
        metrics = container.performance_metrics()
        all_stats = metrics.get_all_stats()

        # 총 에러 수
        total_errors = sum(stat.get("errors", 0) for stat in all_stats.values())

        # 건강 상태 판정
        is_healthy = (
            len(open_cbs) == 0  # Circuit Breaker 모두 정상
            and cost_summary["total_cost_usd"] < 100  # 비용 한도 이내
        )

        return MonitoringResponse(
            success=True,
            data={
                "healthy": is_healthy,
                "circuit_breakers_open": len(open_cbs),
                "open_breakers": open_cbs,
                "total_cost_usd": cost_summary["total_cost_usd"],
                "total_errors": total_errors,
                "total_requests": cost_summary["total_requests"],
            },
            message="시스템 정상" if is_healthy else "주의 필요",
        )
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return MonitoringResponse(
            success=False, data={"healthy": False}, message=f"헬스 체크 실패: {str(e)}"
        )


@router.post("/monitoring/reset", response_model=MonitoringResponse)
async def reset_monitoring():
    """
    모든 모니터링 통계 리셋

    Returns:
        리셋 성공 여부
    """
    try:
        container = _get_container()

        # 비용 추적 리셋
        cost_tracker = container.cost_tracker()
        cost_tracker.reset()

        # 성능 메트릭 리셋
        metrics = container.performance_metrics()
        metrics.reset()

        logger.info("🔄 모니터링 통계 리셋 완료")

        return MonitoringResponse(success=True, data={}, message="모니터링 통계가 리셋되었습니다")
    except Exception as e:
        logger.error(f"모니터링 리셋 실패: {e}")
        return MonitoringResponse(success=False, data={}, message=f"리셋 실패: {str(e)}")
