"""
LangSmith 공식 SDK를 사용한 클라이언트 구현
더 안정적이고 유지보수가 쉬운 대안 솔루션
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .logger import get_logger

logger = get_logger(__name__)

# LangSmith SDK 사용
try:
    from langsmith import Client as LangSmithSDK

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("LangSmith SDK가 설치되지 않음. pip install langsmith를 실행하세요.")


@dataclass
class QueryLogSDK:
    """SDK용 쿼리 로그 데이터 클래스"""

    query_id: str
    user_query: str
    agent_response: str
    timestamp: datetime
    duration_ms: float | None = None
    error: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    session_id: str | None = None
    project_name: str | None = None


class LangSmithSDKClient:
    """
    LangSmith 공식 SDK를 사용한 클라이언트
    더 안정적이고 API 변경에 강건한 구현
    """

    def __init__(self, api_key: str | None = None, api_url: str | None = None):
        """
        클라이언트 초기화

        Args:
            api_key: LangSmith API 키
            api_url: API URL (기본값: https://api.smith.langchain.com)
        """
        if not SDK_AVAILABLE:
            raise ImportError(
                "LangSmith SDK가 설치되지 않았습니다. pip install langsmith를 실행하세요."
            )

        self.api_key = api_key or os.getenv("LANGSMITH_API_KEY")
        self.api_url = api_url or os.getenv("LANGSMITH_API_URL", "https://api.smith.langchain.com")

        if not self.api_key:
            raise ValueError("LangSmith API 키가 필요합니다")

        # 공식 SDK 클라이언트 초기화
        self.client = LangSmithSDK(api_key=self.api_key, api_url=self.api_url)
        logger.info("LangSmith SDK 클라이언트 초기화 완료")

    async def __aenter__(self) -> "LangSmithSDKClient":
        """Async context manager 진입"""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        """Async context manager 종료"""
        # SDK 클라이언트는 명시적 닫기 불필요
        pass

    def list_projects(self) -> list[dict[str, Any]]:
        """
        프로젝트 목록 조회

        Returns:
            프로젝트 목록
        """
        try:
            projects = list(self.client.list_projects())
            result = []
            for p in projects:
                created_at_val = getattr(p, "created_at", None)
                modified_at_val = getattr(p, "modified_at", None)
                result.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "created_at": created_at_val.isoformat() if created_at_val else None,
                        "modified_at": modified_at_val.isoformat() if modified_at_val else None,
                        "description": p.description,
                    }
                )
            return result
        except Exception as e:
            logger.error(f"프로젝트 목록 조회 실패: {e}")
            raise

    def get_query_logs(
        self,
        project_name: str | None = None,
        project_id: str | None = None,
        hours: int = 24,
        limit: int = 100,
        include_errors: bool = True,
    ) -> list[QueryLogSDK]:
        """
        최근 사용자 쿼리 로그 조회

        Args:
            project_name: 프로젝트 이름
            project_id: 프로젝트 ID
            hours: 조회할 시간 범위 (기본 24시간)
            limit: 최대 조회 개수
            include_errors: 에러 로그 포함 여부

        Returns:
            QueryLogSDK 목록
        """
        try:
            # 시간 필터 설정
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours) if hours > 0 else None

            # 필터 설정
            filter_str = "eq(is_root, true)"
            if not include_errors:
                filter_str = f"and({filter_str}, not(has(error)))"

            # SDK를 통한 runs 조회
            runs = list(
                self.client.list_runs(
                    project_name=project_name,
                    project_id=project_id,
                    start_time=start_time,
                    end_time=end_time,
                    filter=filter_str,
                    limit=limit,
                )
            )

            query_logs = []
            for run in runs:
                try:
                    # 쿼리와 응답 추출
                    user_query = ""
                    agent_response = ""

                    # 입력 추출
                    if run.inputs:
                        if isinstance(run.inputs, dict):
                            if "messages" in run.inputs:
                                # Chat 형식
                                messages = run.inputs["messages"]
                                if messages and isinstance(messages, list):
                                    for msg in messages:
                                        if isinstance(msg, dict) and msg.get("role") == "user":
                                            user_query = msg.get("content", "")
                                            break
                            elif "input" in run.inputs:
                                user_query = run.inputs["input"]
                            elif "query" in run.inputs:
                                user_query = run.inputs["query"]
                            elif "question" in run.inputs:
                                user_query = run.inputs["question"]
                        elif isinstance(run.inputs, str):
                            user_query = run.inputs

                    # 출력 추출
                    if run.outputs:
                        if isinstance(run.outputs, dict):
                            if "output" in run.outputs:
                                agent_response = run.outputs["output"]
                            elif "text" in run.outputs:
                                agent_response = run.outputs["text"]
                            elif "answer" in run.outputs:
                                agent_response = run.outputs["answer"]
                            elif "response" in run.outputs:
                                agent_response = run.outputs["response"]
                        elif isinstance(run.outputs, str):
                            agent_response = run.outputs

                    # 시간 계산
                    duration_ms = None
                    if run.end_time and run.start_time:
                        duration_ms = (run.end_time - run.start_time).total_seconds() * 1000

                    query_log = QueryLogSDK(
                        query_id=str(run.id),
                        user_query=user_query,
                        agent_response=agent_response,
                        timestamp=run.start_time,
                        duration_ms=duration_ms,
                        error=run.error if hasattr(run, "error") else None,
                        tags=run.tags if hasattr(run, "tags") else None,
                        metadata=run.extra if hasattr(run, "extra") else None,
                        session_id=str(run.session_id) if run.session_id else None,
                        project_name=project_name,
                    )

                    query_logs.append(query_log)

                except Exception as e:
                    logger.warning(f"Run 파싱 중 오류 (ID: {run.id}): {e}")
                    continue

            logger.info(f"SDK를 통해 {len(query_logs)}개의 로그 조회 완료")
            return query_logs

        except Exception as e:
            logger.error(f"쿼리 로그 조회 실패: {e}")
            raise

    def get_run_details(self, run_id: str) -> dict[str, Any]:
        """
        특정 Run의 상세 정보 조회

        Args:
            run_id: Run ID

        Returns:
            Run 상세 정보
        """
        try:
            run = self.client.read_run(run_id)
            return {
                "id": str(run.id),
                "name": run.name,
                "run_type": run.run_type,
                "start_time": run.start_time.isoformat() if run.start_time else None,
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "error": run.error if hasattr(run, "error") else None,
                "tags": run.tags if hasattr(run, "tags") else [],
                "extra": run.extra if hasattr(run, "extra") else {},
            }
        except Exception as e:
            logger.error(f"Run 상세 정보 조회 실패: {e}")
            raise

    def get_statistics(
        self, project_name: str | None = None, project_id: str | None = None, hours: int = 24
    ) -> dict[str, Any]:
        """
        프로젝트 통계 정보 조회

        Args:
            project_name: 프로젝트 이름
            project_id: 프로젝트 ID
            hours: 통계 기간

        Returns:
            통계 정보
        """
        try:
            # 시간 필터 설정
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            # 모든 루트 runs 조회
            runs = list(
                self.client.list_runs(
                    project_name=project_name,
                    project_id=project_id,
                    start_time=start_time,
                    end_time=end_time,
                    filter="eq(is_root, true)",
                )
            )

            # 통계 계산
            total_count = len(runs)
            error_count = sum(1 for run in runs if hasattr(run, "error") and run.error)
            success_count = total_count - error_count

            durations = []
            for run in runs:
                if run.end_time and run.start_time:
                    duration_ms = (run.end_time - run.start_time).total_seconds() * 1000
                    durations.append(duration_ms)

            avg_duration = sum(durations) / len(durations) if durations else 0
            min_duration = min(durations) if durations else 0
            max_duration = max(durations) if durations else 0

            return {
                "period_hours": hours,
                "total_queries": total_count,
                "success_count": success_count,
                "error_count": error_count,
                "error_rate": error_count / total_count if total_count > 0 else 0,
                "avg_response_time_ms": avg_duration,
                "min_response_time_ms": min_duration,
                "max_response_time_ms": max_duration,
                "queries_per_hour": total_count / hours if hours > 0 else 0,
            }

        except Exception as e:
            logger.error(f"통계 정보 조회 실패: {e}")
            raise

    def _extract_query_response(self, run: dict[str, Any]) -> tuple[str, str | None]:
        """
        Run 데이터에서 사용자 쿼리와 응답 추출

        Args:
            run: Run 딕셔너리 데이터

        Returns:
            (user_query, agent_response) 튜플
        """
        user_query = ""
        agent_response = None

        inputs = run.get("inputs", {})
        outputs = run.get("outputs", {})

        # 입력에서 사용자 쿼리 추출
        if "message" in inputs:
            user_query = inputs["message"]
        elif "messages" in inputs:
            messages = inputs["messages"]
            for msg in messages:
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break
        elif "input" in inputs:
            user_query = inputs["input"]
        elif "query" in inputs:
            user_query = inputs["query"]
        elif "question" in inputs:
            user_query = inputs["question"]
        elif isinstance(inputs, str):
            user_query = inputs

        # 출력에서 응답 추출
        if outputs:
            if "output" in outputs:
                agent_response = outputs["output"]
            elif "text" in outputs:
                agent_response = outputs["text"]
            elif "answer" in outputs:
                agent_response = outputs["answer"]
            elif "response" in outputs:
                agent_response = outputs["response"]
            elif isinstance(outputs, str):
                agent_response = outputs

        return user_query, agent_response

    async def get_trace_hierarchy(self, trace_id: str) -> list[dict[str, Any]]:
        """
        특정 Trace의 전체 계층 구조 조회

        Args:
            trace_id: Trace ID

        Returns:
            Trace에 속한 모든 Run 목록 (계층 구조 포함)
        """
        try:
            # SDK를 통해 특정 trace의 모든 runs 조회
            runs = list(self.client.list_runs(filter=f'eq(trace_id, "{trace_id}")', limit=1000))

            # 계층 구조로 재구성
            runs_dict: dict[str, dict[str, Any]] = {}
            for run in runs:
                run_data: dict[str, Any] = {
                    "id": str(run.id),
                    "name": run.name,
                    "run_type": run.run_type,
                    "start_time": run.start_time.isoformat() if run.start_time else None,
                    "end_time": run.end_time.isoformat() if run.end_time else None,
                    "inputs": run.inputs,
                    "outputs": run.outputs,
                    "error": run.error if hasattr(run, "error") else None,
                    "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
                    "children": [],
                }
                runs_dict[str(run.id)] = run_data

            # 부모-자식 관계 구성
            root_runs = []
            for run_data in runs_dict.values():
                parent_id = run_data.get("parent_run_id")
                if parent_id and parent_id in runs_dict:
                    runs_dict[parent_id]["children"].append(run_data)
                else:
                    root_runs.append(run_data)

            return root_runs

        except Exception as e:
            logger.error(f"Trace 계층 구조 조회 실패: {e}")
            raise


# SDK 사용 예제
if __name__ == "__main__":
    # 클라이언트 초기화
    client = LangSmithSDKClient()

    # 프로젝트 목록 조회
    projects = client.list_projects()
    print(f"프로젝트 수: {len(projects)}")

    # 최근 로그 조회
    if projects:
        logs = client.get_query_logs(project_name=projects[0]["name"], hours=24, limit=10)
        print(f"로그 수: {len(logs)}")

        # 통계 조회
        stats = client.get_statistics(project_name=projects[0]["name"], hours=24)
        print(f"통계: {stats}")
