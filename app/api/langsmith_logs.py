"""
LangSmith 로그 API 엔드포인트
사용자 쿼리 및 응답 로그 조회 API
"""

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.lib import LangSmithSDKClient, QueryLogSDK

LangSmithClient = LangSmithSDKClient
QueryLog = QueryLogSDK
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/langsmith", tags=["LangSmith Logs"])


class QueryLogResponse(BaseModel):
    """쿼리 로그 응답 모델"""

    query_id: str = Field(description="쿼리 고유 ID")
    user_query: str = Field(description="사용자 질문")
    agent_response: str | None = Field(description="에이전트 응답")
    timestamp: datetime = Field(description="쿼리 시간")
    duration_ms: float | None = Field(description="응답 소요 시간(밀리초)")
    error: str | None = Field(description="에러 메시지")
    tags: list[str] = Field(default_factory=list, description="태그 목록")
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    session_id: str | None = Field(description="세션 ID")


class ProjectResponse(BaseModel):
    """프로젝트 정보 응답 모델"""

    id: str = Field(description="프로젝트 ID")
    name: str = Field(description="프로젝트 이름")
    created_at: datetime | None = Field(description="생성 시간")
    metadata: dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class StatisticsResponse(BaseModel):
    """통계 정보 응답 모델"""

    period_hours: int = Field(description="통계 기간(시간)")
    total_queries: int = Field(description="전체 쿼리 수")
    success_count: int = Field(description="성공 쿼리 수")
    error_count: int = Field(description="실패 쿼리 수")
    error_rate: float = Field(description="에러율")
    avg_response_time_ms: float = Field(description="평균 응답 시간(밀리초)")
    min_response_time_ms: float = Field(description="최소 응답 시간(밀리초)")
    max_response_time_ms: float = Field(description="최대 응답 시간(밀리초)")
    queries_per_hour: float = Field(description="시간당 쿼리 수")


class QueryDetailResponse(BaseModel):
    """쿼리 상세 정보 응답 모델"""

    query_id: str = Field(description="쿼리 ID (trace_id)")
    user_query: str = Field(description="사용자 질문")
    agent_response: str | None = Field(description="에이전트 응답")
    timestamp: datetime = Field(description="쿼리 시간")
    duration_ms: float | None = Field(description="응답 소요 시간")
    error: str | None = Field(description="에러 메시지")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_hierarchy: list[dict[str, Any]] | None = Field(description="Trace 계층 구조")


async def get_langsmith_client() -> LangSmithClient:
    """LangSmith 클라이언트 인스턴스 생성"""
    client = LangSmithClient()
    return client


@router.get("/test-runs")
async def test_runs(
    project_name: str = Query("rag4184", description="프로젝트 이름"),
    limit: int = Query(5, description="조회 개수"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> dict[str, Any]:
    """
    Run 조회 테스트 - 직접 API 호출

    Returns:
        Run 조회 결과 또는 에러
    """
    try:
        async with client:
            project_id = os.getenv("LANGSMITH_PROJECT_ID", "default-project-id")
            url = f"{client.api_url}/runs"
            headers = client._get_headers()  # type: ignore[attr-defined]
            params = {"session": project_id, "limit": limit, "is_root": "true"}
            logger.info(f"테스트 요청 URL: {url}")
            logger.info(f"테스트 파라미터: {params}")
            response = await client.client.get(url, headers=headers, params=params)  # type: ignore[attr-defined]
            response.raise_for_status()
            runs = response.json()
            return {
                "status": "success",
                "url": url,
                "params": params,
                "run_count": len(runs) if isinstance(runs, list) else len(runs.get("runs", [])),
                "sample": runs[:2] if isinstance(runs, list) else runs.get("runs", [])[:2],
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"테스트 실패: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "error_code": e.response.status_code,
            "error_message": e.response.text,
            "url": str(e.request.url),
            "method": e.request.method,
        }
    except Exception as e:
        logger.error(f"테스트 중 오류: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/test-post-query")
async def test_post_query(
    project_name: str = Query("rag4184", description="프로젝트 이름"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> dict[str, Any]:
    """
    POST /runs/query 엔드포인트 직접 테스트

    Returns:
        테스트 결과
    """
    try:
        async with client:
            # 기본 프로젝트 ID를 환경변수에서 가져옴
            default_project_id = os.getenv("LANGSMITH_PROJECT_ID", "default-project-id")
            known_projects = {"rag4184": default_project_id}
            session_id = known_projects.get(project_name)
            if not session_id:
                return {"error": f"프로젝트 '{project_name}'을 찾을 수 없음"}
            url = f"{client.api_url}/runs/query"
            headers = client._get_headers()  # type: ignore[attr-defined]
            request_body = {
                "session": [session_id],
                "filter": "eq(is_root, true)",
                "limit": 5,
                "offset": 0,
            }
            logger.info(f"직접 POST 테스트 - URL: {url}")
            logger.info(f"요청 body: {request_body}")
            response = await client.client.post(url, headers=headers, json=request_body)  # type: ignore[attr-defined]
            response.raise_for_status()
            result = response.json()
            return {
                "status": "success",
                "url": url,
                "method": "POST",
                "body": request_body,
                "result_count": (
                    len(result) if isinstance(result, list) else len(result.get("runs", []))
                ),
                "sample": result[:2] if isinstance(result, list) else result.get("runs", [])[:2],
            }
    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "error_code": e.response.status_code,
            "error_message": e.response.text,
            "url": str(e.request.url),
            "method": e.request.method,
            "body": request_body,
        }
    except Exception as e:
        logger.error(f"Unexpected error in test-post-query: {e}", exc_info=True)
        return {
            "status": "error",
            "error_type": "INTERNAL_ERROR",
            "message": "An unexpected error occurred during query execution",
        }


@router.get("/test-runs-no-time")
async def test_runs_no_time(
    project_name: str = Query("rag4184", description="프로젝트 이름"),
    limit: int = Query(5, description="조회 개수"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> dict[str, Any]:
    """
    시간 필터 없이 Run 조회 테스트

    Args:
        project_name: 프로젝트 이름
        limit: 조회 개수

    Returns:
        테스트 결과
    """
    try:
        async with client:
            logs = client.get_query_logs(
                project_name=project_name, hours=0, limit=limit, include_errors=True
            )
            return {
                "status": "success",
                "project_name": project_name,
                "log_count": len(logs),
                "logs": [
                    {
                        "query_id": log.query_id,
                        "user_query": log.user_query[:100] if log.user_query else None,
                        "agent_response": log.agent_response[:100] if log.agent_response else None,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "duration_ms": log.duration_ms,
                        "error": log.error,
                    }
                    for log in logs
                ],
            }
    except Exception as e:
        logger.error(f"시간 필터 없는 테스트 실패: {e}")
        return {"status": "error", "error": str(e), "project_name": project_name}


@router.get("/test-connection")
async def test_connection(
    client: LangSmithClient = Depends(get_langsmith_client),
) -> dict[str, Any]:
    """
    LangSmith API 연결 테스트 및 디버깅

    Returns:
        연결 상태 및 디버깅 정보
    """
    try:
        async with client:
            api_key = client.api_key
            masked_key = (
                f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else "Not Set"
            )
            projects = []
            try:
                projects_data = client.list_projects()
                for p in projects_data:
                    projects.append({"id": p.get("id", ""), "name": p.get("name", "")})
            except Exception as proj_err:
                logger.error(f"프로젝트 조회 에러: {proj_err}")
            return {
                "status": "connected",
                "api_url": client.api_url,
                "api_key_status": "configured" if api_key else "missing",
                "api_key_preview": masked_key,
                "tenant_id": getattr(client, "tenant_id", "Not Set"),
                "available_projects": projects,
                "project_count": len(projects),
                "message": "LangSmith API 연결 성공",
            }
    except Exception as e:
        logger.error(f"연결 테스트 실패: {e}")
        return {"status": "error", "error": str(e), "message": "LangSmith API 연결 실패"}


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    client: LangSmithClient = Depends(get_langsmith_client),
) -> list[ProjectResponse]:
    """
    LangSmith 프로젝트 목록 조회

    Returns:
        프로젝트 목록
    """
    try:
        async with client:
            projects = client.list_projects()
            result = []
            for project in projects:
                result.append(
                    ProjectResponse(
                        id=project.get("id", ""),
                        name=project.get("name", ""),
                        created_at=project.get("created_at"),
                        metadata=project.get("metadata", {}),
                    )
                )
            return result
    except Exception as e:
        logger.error(f"프로젝트 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"프로젝트 목록 조회 실패: {str(e)}") from e


@router.get("/logs", response_model=list[QueryLogResponse])
async def get_query_logs(
    project_name: str | None = Query(None, description="프로젝트 이름"),
    project_id: str | None = Query(None, description="프로젝트 ID"),
    hours: int = Query(24, description="조회 기간(시간)", ge=1, le=720),
    limit: int = Query(100, description="최대 조회 개수", ge=1, le=1000),
    include_errors: bool = Query(True, description="에러 로그 포함 여부"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> list[QueryLogResponse]:
    """
    최근 사용자 쿼리 로그 조회

    Args:
        project_name: 프로젝트 이름 (선택)
        project_id: 프로젝트 ID (선택)
        hours: 조회할 시간 범위 (기본 24시간)
        limit: 최대 조회 개수 (기본 100개)
        include_errors: 에러 로그 포함 여부

    Returns:
        쿼리 로그 목록
    """
    if not project_name and (not project_id):
        raise HTTPException(status_code=400, detail="프로젝트 이름 또는 ID가 필요합니다")
    try:
        async with client:
            logs = client.get_query_logs(
                project_name=project_name,
                project_id=project_id,
                hours=hours,
                limit=limit,
                include_errors=include_errors,
            )
            result = []
            for log in logs:
                result.append(
                    QueryLogResponse(
                        query_id=log.query_id,
                        user_query=log.user_query,
                        agent_response=log.agent_response,
                        timestamp=log.timestamp,
                        duration_ms=log.duration_ms,
                        error=log.error,
                        tags=log.tags or [],
                        metadata=log.metadata or {},
                        session_id=log.session_id,
                    )
                )
            return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"쿼리 로그 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"쿼리 로그 조회 실패: {str(e)}") from e


@router.get("/logs/{trace_id}", response_model=QueryDetailResponse)
async def get_query_detail(
    trace_id: str,
    include_hierarchy: bool = Query(False, description="Trace 계층 구조 포함 여부"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> QueryDetailResponse:
    """
    특정 쿼리의 상세 정보 조회

    Args:
        trace_id: Trace ID (쿼리 ID)
        include_hierarchy: Trace 전체 계층 구조 포함 여부

    Returns:
        쿼리 상세 정보
    """
    try:
        async with client:
            run_details = client.get_run_details(run_id=trace_id)
            user_query, agent_response = client._extract_query_response(run_details)
            start = datetime.fromisoformat(run_details["start_time"].replace("Z", "+00:00"))
            duration_ms = None
            if run_details.get("end_time"):
                end = datetime.fromisoformat(run_details["end_time"].replace("Z", "+00:00"))
                duration_ms = (end - start).total_seconds() * 1000
            trace_hierarchy = None
            if include_hierarchy:
                trace_hierarchy = await client.get_trace_hierarchy(trace_id)
            return QueryDetailResponse(
                query_id=trace_id,
                user_query=user_query,
                agent_response=agent_response,
                timestamp=start,
                duration_ms=duration_ms,
                error=run_details.get("error"),
                tags=run_details.get("tags", []),
                metadata=run_details.get("metadata", {}),
                trace_hierarchy=trace_hierarchy,
            )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"쿼리 상세 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"쿼리 상세 정보 조회 실패: {str(e)}") from e


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    project_name: str | None = Query(None, description="프로젝트 이름"),
    project_id: str | None = Query(None, description="프로젝트 ID"),
    hours: int = Query(24, description="통계 기간(시간)", ge=1, le=720),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> StatisticsResponse:
    """
    프로젝트 통계 정보 조회

    Args:
        project_name: 프로젝트 이름 (선택)
        project_id: 프로젝트 ID (선택)
        hours: 통계 기간 (기본 24시간)

    Returns:
        통계 정보
    """
    if not project_name and (not project_id):
        raise HTTPException(status_code=400, detail="프로젝트 이름 또는 ID가 필요합니다")
    try:
        async with client:
            stats = client.get_statistics(
                project_name=project_name, project_id=project_id, hours=hours
            )
            return StatisticsResponse(**stats)
    except Exception as e:
        logger.error(f"통계 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 정보 조회 실패: {str(e)}") from e


@router.post("/refresh-cache")
async def refresh_cache(
    project_name: str | None = Query(None, description="프로젝트 이름"),
    project_id: str | None = Query(None, description="프로젝트 ID"),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> dict[str, Any]:
    """
    로그 캐시 새로고침 (향후 캐싱 구현 시 사용)

    Args:
        project_name: 프로젝트 이름 (선택)
        project_id: 프로젝트 ID (선택)

    Returns:
        새로고침 결과
    """
    if not project_name and (not project_id):
        raise HTTPException(status_code=400, detail="프로젝트 이름 또는 ID가 필요합니다")
    try:
        async with client:
            logs = client.get_query_logs(
                project_name=project_name, project_id=project_id, hours=1, limit=10
            )
            return {
                "status": "success",
                "message": "캐시가 새로고침되었습니다",
                "updated_count": len(logs),
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        logger.error(f"캐시 새로고침 실패: {e}")
        raise HTTPException(status_code=500, detail=f"캐시 새로고침 실패: {str(e)}") from e


@router.get("/search", response_model=list[QueryLogResponse])
async def search_logs(
    query: str = Query(..., description="검색 키워드"),
    project_name: str | None = Query(None, description="프로젝트 이름"),
    project_id: str | None = Query(None, description="프로젝트 ID"),
    hours: int = Query(24, description="조회 기간(시간)", ge=1, le=720),
    limit: int = Query(100, description="최대 조회 개수", ge=1, le=1000),
    client: LangSmithClient = Depends(get_langsmith_client),
) -> list[QueryLogResponse]:
    """
    쿼리 로그 검색
    사용자 쿼리나 응답 내용에서 키워드 검색

    Args:
        query: 검색 키워드
        project_name: 프로젝트 이름 (선택)
        project_id: 프로젝트 ID (선택)
        hours: 조회 기간
        limit: 최대 결과 개수

    Returns:
        검색 결과
    """
    if not project_name and (not project_id):
        raise HTTPException(status_code=400, detail="프로젝트 이름 또는 ID가 필요합니다")
    try:
        async with client:
            logs = client.get_query_logs(
                project_name=project_name, project_id=project_id, hours=hours, limit=limit * 2
            )
            query_lower = query.lower()
            filtered_logs = []
            for log in logs:
                if query_lower in log.user_query.lower() or (
                    log.agent_response and query_lower in log.agent_response.lower()
                ):
                    filtered_logs.append(
                        QueryLogResponse(
                            query_id=log.query_id,
                            user_query=log.user_query,
                            agent_response=log.agent_response,
                            timestamp=log.timestamp,
                            duration_ms=log.duration_ms,
                            error=log.error,
                            tags=log.tags or [],
                            metadata=log.metadata or {},
                            session_id=log.session_id,
                        )
                    )
                    if len(filtered_logs) >= limit:
                        break
            return filtered_logs
    except Exception as e:
        logger.error(f"로그 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"로그 검색 실패: {str(e)}") from e
