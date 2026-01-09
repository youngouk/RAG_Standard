"""
데이터 정합성 테스트

Memory-DB 동기화 실패 시나리오를 검증하여
데이터 손실 및 불일치를 방지합니다.

테스트 범위:
1. PostgreSQL 저장 실패 시 메모리-DB 불일치
2. DB 장애 중에도 세션 생성 가능 (Graceful Degradation)
3. DB 복구 후 정상 저장 재개
4. 타임아웃 시나리오 (2초 초과)

⚠️ 현실 시나리오:
- 14:00 사용자 100명 세션 생성
- 14:05 PostgreSQL 장애 발생
- 14:10 세션은 메모리에만 존재 (DB 저장 실패)
- 15:00 서버 재시작 → 모든 세션 데이터 손실 ⚠️

작성일: 2026-01-06
"""

import asyncio
from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestDataConsistency:
    """데이터 정합성 테스트 - Memory-DB 동기화"""

    @pytest.fixture
    def session_service(self):
        """SessionService 인스턴스"""
        from app.lib.config_loader import load_config
        from app.modules.core.session.services.session_service import SessionService

        config = load_config()
        service = SessionService(config=config)
        return service

    @pytest.mark.asyncio
    async def test_session_created_in_memory_despite_db_failure(
        self, session_service
    ) -> None:
        """
        DB 저장 실패해도 세션 생성 계속 (Graceful Degradation)

        Given: PostgreSQL 저장 실패
        When: 세션 생성 요청
        Then: 메모리에는 세션 존재, DB 저장 실패 로그
        """
        # Mock DB 저장 실패
        original_save = session_service._save_session_to_db

        async def mock_save_fail(*args, **kwargs):
            raise Exception("PostgreSQL connection refused")

        session_service._save_session_to_db = mock_save_fail

        # 세션 생성 (DB 저장 실패해도 성공해야 함)
        result = await session_service.create_session(
            session_id="db-fail-test",
            metadata={"metadata": {"ip_address": "127.0.0.1"}},
        )

        session_id = result["session_id"]

        # 검증: 메모리에 세션 존재
        assert session_id in session_service.sessions
        assert session_service.sessions[session_id]["session_id"] == session_id

        # 검증: 세션 조회 가능 (서비스 계속 동작)
        session_result = await session_service.get_session(session_id)
        assert session_result["is_valid"] is True

        # 원상 복구
        session_service._save_session_to_db = original_save

    @pytest.mark.asyncio
    async def test_db_save_timeout_with_direct_call(self, session_service) -> None:
        """
        DB 저장 타임아웃 직접 호출 테스트

        Given: _save_session_to_db()를 3초 지연으로 Mock
        When: asyncio.wait_for(timeout=2.0) 호출
        Then: TimeoutError 발생, 세션은 메모리에 존재
        """
        # Mock DB 저장 느린 응답
        async def mock_slow_save(*args, **kwargs):
            await asyncio.sleep(3)  # 3초 지연 (타임아웃 2초보다 김)

        session_service._save_session_to_db = mock_slow_save

        # 세션 생성 (메모리)
        result = await session_service.create_session(session_id="timeout-direct-test")
        session_id = result["session_id"]

        # 메모리에 세션 존재
        assert session_id in session_service.sessions

        # _save_session_to_db() 직접 호출 (타임아웃 테스트)
        import time

        location_data = {"ip_hash": "test", "country": "KR"}
        metadata = {"metadata": {"ip_address": "127.0.0.1"}}

        start = time.time()
        timeout_occurred = False

        try:
            await asyncio.wait_for(
                session_service._save_session_to_db(session_id, location_data, metadata),
                timeout=2.0,
            )
        except TimeoutError:
            timeout_occurred = True

        elapsed = time.time() - start

        # 검증: 타임아웃 발생
        assert timeout_occurred is True

        # 검증: 2초 타임아웃 발생 (약간의 오버헤드 허용)
        assert 2.0 <= elapsed <= 2.5, f"타임아웃 시간이 비정상: {elapsed:.2f}초"

    @pytest.mark.asyncio
    async def test_db_recovery_resumes_normal_save(self, session_service) -> None:
        """
        DB 복구 후 정상 저장 재개

        Given: DB 장애 → 복구
        When: 세션 생성
        Then: 복구 후 세션은 정상 저장
        """
        # 1. DB 저장 실패 상태
        original_save = session_service._save_session_to_db

        async def mock_save_fail(*args, **kwargs):
            raise Exception("DB down")

        session_service._save_session_to_db = mock_save_fail

        # 첫 세션 생성 (DB 실패)
        result1 = await session_service.create_session(
            session_id="recovery-test-1",
            metadata={"metadata": {"ip_address": "127.0.0.1"}},
        )
        session_id1 = result1["session_id"]

        # 메모리에만 존재
        assert session_id1 in session_service.sessions

        # 2. DB 복구 (Mock 제거)
        session_service._save_session_to_db = original_save

        # 3. 두 번째 세션 생성 (DB 정상)
        result2 = await session_service.create_session(
            session_id="recovery-test-2",
            metadata={"metadata": {"ip_address": "127.0.0.1"}},
        )
        session_id2 = result2["session_id"]

        # 메모리에 존재
        assert session_id2 in session_service.sessions

        # 검증: 두 세션 모두 조회 가능
        assert (await session_service.get_session(session_id1))["is_valid"] is True
        assert (await session_service.get_session(session_id2))["is_valid"] is True

    @pytest.mark.asyncio
    async def test_concurrent_sessions_with_db_failures(self, session_service) -> None:
        """
        동시 세션 생성 중 일부 DB 실패

        Given: 10개 동시 세션 생성
        When: 일부 DB 저장 실패
        Then: 모든 세션 메모리에 생성됨 (Graceful Degradation)
        """
        # Mock DB 저장 (50% 실패율)
        call_count = 0

        async def mock_save_random_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("DB intermittent failure")

        session_service._save_session_to_db = mock_save_random_fail

        # 10개 동시 세션 생성
        tasks = [session_service.create_session(session_id=None) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # 검증: 모든 세션 생성 성공
        assert len(results) == 10
        session_ids = [r["session_id"] for r in results]

        # 검증: 모든 세션 메모리에 존재
        for session_id in session_ids:
            assert session_id in session_service.sessions

    @pytest.mark.asyncio
    async def test_session_stats_update_despite_db_failure(
        self, session_service
    ) -> None:
        """
        DB 실패해도 통계 업데이트 계속

        Given: DB 저장 실패
        When: 세션 생성
        Then: stats['total_sessions'] 증가
        """
        # Mock DB 저장 실패
        async def mock_save_fail(*args, **kwargs):
            raise Exception("DB error")

        session_service._save_session_to_db = mock_save_fail

        # 초기 통계
        initial_stats = await session_service.get_stats()
        initial_total = initial_stats["total_sessions"]

        # 세션 생성 (DB 실패)
        await session_service.create_session(session_id=None)

        # 통계 확인
        final_stats = await session_service.get_stats()
        final_total = final_stats["total_sessions"]

        # 검증: 통계 증가
        assert final_total == initial_total + 1


@pytest.mark.integration
class TestDataConsistencyEdgeCases:
    """데이터 정합성 엣지 케이스 테스트"""

    @pytest.fixture
    def session_service(self):
        """SessionService 인스턴스"""
        from app.lib.config_loader import load_config
        from app.modules.core.session.services.session_service import SessionService

        config = load_config()
        service = SessionService(config=config)
        return service

    @pytest.mark.asyncio
    async def test_db_save_timeout_cancellation(self, session_service) -> None:
        """
        DB 저장 타임아웃 후 취소

        Given: DB 저장이 10초 걸림 (타임아웃 2초)
        When: 타임아웃 발생
        Then: asyncio.wait_for가 TimeoutError 발생, 세션 생성은 계속
        """
        # Mock 느린 DB 저장
        async def mock_very_slow_save(*args, **kwargs):
            await asyncio.sleep(10)  # 10초 지연

        session_service._save_session_to_db = mock_very_slow_save

        # 세션 생성 (타임아웃 발생)
        result = await session_service.create_session(
            session_id="timeout-cancel-test",
            metadata={"metadata": {"ip_address": "127.0.0.1"}},
        )

        session_id = result["session_id"]

        # 검증: 세션 생성 성공
        assert session_id in session_service.sessions

    @pytest.mark.asyncio
    async def test_db_not_initialized(self, session_service) -> None:
        """
        DB 초기화 안 된 경우

        Given: DB가 초기화되지 않음
        When: 세션 생성
        Then: DB 저장 스킵, 세션 생성 성공
        """
        # Mock DB 초기화 안 됨
        with patch(
            "app.infrastructure.persistence.connection.db_manager._initialized", False
        ):
            # 세션 생성
            result = await session_service.create_session(
                session_id="no-db-test",
                metadata={"metadata": {"ip_address": "127.0.0.1"}},
            )

            session_id = result["session_id"]

            # 검증: 세션 생성 성공
            assert session_id in session_service.sessions

    @pytest.mark.asyncio
    async def test_memory_session_survives_db_restart(self, session_service) -> None:
        """
        DB 재시작 중에도 메모리 세션 유지

        Given: 메모리에 세션 생성
        When: DB 재시작 (Mock)
        Then: 메모리 세션은 계속 사용 가능
        """
        # 1. DB 정상 상태에서 세션 생성
        result = await session_service.create_session(session_id="db-restart-test")
        session_id = result["session_id"]

        # 2. DB 다운 시뮬레이션 (Mock)
        async def mock_db_down(*args, **kwargs):
            raise Exception("DB connection lost")

        session_service._save_session_to_db = mock_db_down

        # 3. 세션 조회 (여전히 가능)
        session_result = await session_service.get_session(session_id)
        assert session_result["is_valid"] is True

        # 4. 새 세션 생성 (DB 다운이지만 성공)
        result2 = await session_service.create_session(session_id="during-db-down")
        session_id2 = result2["session_id"]

        # 검증: 메모리에서 동작
        assert session_id2 in session_service.sessions
