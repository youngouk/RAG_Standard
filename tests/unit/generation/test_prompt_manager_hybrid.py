"""
PromptManager Hybrid Storage 테스트

테스트 범위:
1. PostgreSQL → JSON 폴백 (읽기/쓰기)
2. 중복 프롬프트 에러 처리
3. 업데이트/삭제 작업 검증
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.persistence.prompt_repository import DuplicatePromptError
from app.models.prompts import PromptCreate, PromptResponse
from app.modules.core.generation.prompt_manager import PromptManager


@pytest.mark.unit
class TestPromptManagerHybrid:
    """Hybrid Storage 테스트"""

    @pytest.fixture
    def manager_with_db(self):
        """PostgreSQL + JSON 하이브리드 매니저"""
        # Mock Repository
        mock_repository = AsyncMock()

        manager = PromptManager(
            storage_path="./data/prompts",
            repository=mock_repository,
            use_database=True,
        )
        return manager

    @pytest.mark.asyncio
    async def test_get_prompt_falls_back_to_json_on_db_failure(self, manager_with_db):
        """
        PostgreSQL 조회 실패 시 JSON 폴백

        Given: PostgreSQL 조회 실패
        When: get_prompt() 호출
        Then: JSON 파일에서 조회
        """
        # Mock: DB 실패
        manager_with_db.repository.get_by_id.side_effect = Exception("DB connection lost")

        # Mock: JSON 폴백 성공
        with patch.object(manager_with_db, "_get_prompt_from_json") as mock_json:
            mock_json.return_value = PromptResponse(
                id="p1",
                name="test_prompt",
                content="JSON 폴백 성공",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            result = await manager_with_db.get_prompt(prompt_id="p1")

            # 검증: JSON 폴백 호출됨
            assert result is not None
            assert result.content == "JSON 폴백 성공"
            mock_json.assert_called_once_with("p1", None)

    @pytest.mark.asyncio
    async def test_create_prompt_handles_duplicate_error(self, manager_with_db):
        """
        중복 프롬프트 생성 시 에러 처리

        Given: 동일한 이름의 프롬프트 이미 존재
        When: create_prompt() 호출
        Then: ValueError 발생 (DuplicatePromptError → ValueError 변환)
        """
        # Mock: 중복 에러
        manager_with_db.repository.create.side_effect = DuplicatePromptError(
            "Prompt with name 'test' already exists"
        )

        prompt_data = PromptCreate(
            name="test",
            content="중복 테스트",
        )

        with pytest.raises(ValueError) as exc_info:
            await manager_with_db.create_prompt(prompt_data)

        # 검증: 중복 에러 메시지
        assert "already exists" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_prompt_syncs_to_json(self, manager_with_db):
        """
        프롬프트 업데이트 시 JSON 동기화

        Given: PostgreSQL 업데이트 성공
        When: update_prompt() 호출
        Then: JSON 파일에도 동기화
        """
        # Mock: DB 업데이트 성공
        updated_prompt = PromptResponse(
            id="p1",
            name="updated_prompt",
            content="업데이트됨",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        manager_with_db.repository.update.return_value = updated_prompt

        # Mock: JSON 동기화
        with patch.object(manager_with_db, "_sync_to_json") as mock_sync:
            result = await manager_with_db.update_prompt(
                prompt_id="p1",
                update_data={"content": "업데이트됨"},
            )

            # 검증: JSON 동기화 호출됨
            assert result.content == "업데이트됨"
            mock_sync.assert_called_once_with(updated_prompt)
