"""
프롬프트 데이터 Repository

PostgreSQL을 사용하여 프롬프트 데이터를 영구 저장하고 관리합니다.
Repository 패턴을 구현하여 데이터 접근 계층을 캡슐화합니다.

주요 기능:
- 프롬프트 데이터 CRUD (생성, 조회, 수정, 삭제)
- 카테고리별 필터링 및 검색
- 활성 프롬프트 조회
"""

from __future__ import annotations

import builtins
import uuid
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.exc import IntegrityError

from app.lib.logger import get_logger
from app.models.prompts import PromptCreate, PromptListResponse, PromptResponse, PromptUpdate

from .connection import db_manager
from .models import PromptModel

logger = get_logger(__name__)


class DuplicatePromptError(Exception):
    """동일한 이름의 프롬프트가 이미 존재할 때 발생"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"프롬프트 '{name}'이(가) 이미 존재합니다")


class PromptNotFoundError(Exception):
    """프롬프트를 찾을 수 없을 때 발생"""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"프롬프트 '{identifier}'을(를) 찾을 수 없습니다")


class PromptRepository:
    """
    프롬프트 데이터 Repository

    PostgreSQL을 사용한 프롬프트 데이터의 영구 저장 및 관리를 담당합니다.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        프롬프트 Repository 초기화

        Args:
            config: 설정 정보 (선택적)
        """
        self.config = config or {}
        self.db_manager = db_manager

    async def initialize(self) -> None:
        """모듈 초기화 (비동기)"""
        import os

        # 테스트 환경에서는 PostgreSQL 초기화 스킵
        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.info("⚠️ 테스트 환경: PostgreSQL 프롬프트 모듈 초기화 스킵")
            return

        logger.info("PostgreSQL 프롬프트 모듈 초기화 중...")

        # 데이터베이스 연결 초기화
        await self.db_manager.initialize()

        # 테이블 생성 (필요시)
        await self.db_manager.create_tables()

        logger.info("PostgreSQL 프롬프트 모듈 초기화 완료")

    async def create(self, prompt_data: PromptCreate) -> PromptResponse:
        """
        새 프롬프트 생성

        Args:
            prompt_data: 프롬프트 생성 데이터

        Returns:
            생성된 프롬프트 정보

        Raises:
            DuplicatePromptError: 동일한 이름의 프롬프트가 이미 존재
        """
        async with self.db_manager.get_session() as session:
            # 중복 체크
            existing = await session.execute(
                select(PromptModel).where(PromptModel.name == prompt_data.name)
            )
            if existing.scalar_one_or_none():
                raise DuplicatePromptError(prompt_data.name)

            # ID 생성 (제공되지 않은 경우)
            prompt_id = prompt_data.id or str(uuid.uuid4())

            # 모델 생성
            db_prompt = PromptModel(
                id=prompt_id,
                name=prompt_data.name,
                content=prompt_data.content,
                description=prompt_data.description,
                category=prompt_data.category or "system",
                is_active=prompt_data.is_active,
                extra_metadata=prompt_data.metadata or {},
            )

            try:
                session.add(db_prompt)
                await session.commit()
                await session.refresh(db_prompt)

                logger.info(
                    "✅ 프롬프트 생성 완료",
                    prompt_id=db_prompt.id,
                    name=db_prompt.name,
                    category=db_prompt.category,
                )

                return PromptResponse(**db_prompt.to_dict())

            except IntegrityError as e:
                await session.rollback()
                logger.error("프롬프트 생성 실패 (무결성 오류)", error=str(e))
                raise DuplicatePromptError(prompt_data.name)

    async def get_by_id(self, prompt_id: str) -> PromptResponse | None:
        """
        ID로 프롬프트 조회

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            프롬프트 정보 (없으면 None)
        """
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(PromptModel).where(PromptModel.id == prompt_id))
            prompt = result.scalar_one_or_none()

            if prompt:
                return PromptResponse(**prompt.to_dict())
            return None

    async def get_by_name(self, name: str) -> PromptResponse | None:
        """
        이름으로 프롬프트 조회

        Args:
            name: 프롬프트 이름

        Returns:
            프롬프트 정보 (없으면 None)
        """
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(PromptModel).where(PromptModel.name == name))
            prompt = result.scalar_one_or_none()

            if prompt:
                return PromptResponse(**prompt.to_dict())
            return None

    async def list(
        self,
        category: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> PromptListResponse:
        """
        프롬프트 목록 조회 (필터링, 페이지네이션 지원)

        Args:
            category: 카테고리 필터
            is_active: 활성화 상태 필터
            search: 이름 검색 (부분 일치)
            page: 페이지 번호 (1부터 시작)
            per_page: 페이지당 항목 수

        Returns:
            프롬프트 목록 및 메타데이터
        """
        async with self.db_manager.get_session() as session:
            # 기본 쿼리
            query = select(PromptModel)
            count_query = select(PromptModel)

            # 필터 적용
            filters = []
            if category:
                filters.append(PromptModel.category == category)
            if is_active is not None:
                filters.append(PromptModel.is_active == is_active)
            if search:
                filters.append(PromptModel.name.ilike(f"%{search}%"))

            if filters:
                query = query.where(and_(*filters))
                count_query = count_query.where(and_(*filters))

            # 정렬 (최신순)
            query = query.order_by(desc(PromptModel.updated_at))

            # 전체 개수 조회
            total_result = await session.execute(count_query)
            total = len(total_result.scalars().all())

            # 페이지네이션
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)

            # 데이터 조회
            result = await session.execute(query)
            prompts = result.scalars().all()

            return PromptListResponse(
                prompts=[PromptResponse(**p.to_dict()) for p in prompts],
                total=total,
                page=page,
                page_size=per_page,
            )

    async def update(self, prompt_id: str, update_data: PromptUpdate) -> PromptResponse:
        """
        프롬프트 수정

        Args:
            prompt_id: 프롬프트 ID
            update_data: 수정할 데이터

        Returns:
            수정된 프롬프트 정보

        Raises:
            PromptNotFoundError: 프롬프트를 찾을 수 없음
            DuplicatePromptError: 이름 중복
        """
        async with self.db_manager.get_session() as session:
            # 프롬프트 조회
            result = await session.execute(select(PromptModel).where(PromptModel.id == prompt_id))
            prompt = result.scalar_one_or_none()

            if not prompt:
                raise PromptNotFoundError(prompt_id)

            # 업데이트 필드 적용
            update_dict = update_data.model_dump(exclude_unset=True)

            # 이름 중복 체크 (변경되는 경우)
            if "name" in update_dict and update_dict["name"] != prompt.name:
                existing = await session.execute(
                    select(PromptModel).where(PromptModel.name == update_dict["name"])
                )
                if existing.scalar_one_or_none():
                    raise DuplicatePromptError(update_dict["name"])

            # metadata는 extra_metadata로 매핑
            if "metadata" in update_dict:
                update_dict["extra_metadata"] = update_dict.pop("metadata")

            # 필드 업데이트
            for key, value in update_dict.items():
                setattr(prompt, key, value)

            try:
                await session.commit()
                await session.refresh(prompt)

                logger.info(
                    "✅ 프롬프트 수정 완료",
                    prompt_id=prompt.id,
                    name=prompt.name,
                )

                return PromptResponse(**prompt.to_dict())

            except IntegrityError as e:
                await session.rollback()
                logger.error("프롬프트 수정 실패 (무결성 오류)", error=str(e))
                raise

    async def delete(self, prompt_id: str) -> bool:
        """
        프롬프트 삭제

        Args:
            prompt_id: 프롬프트 ID

        Returns:
            삭제 성공 여부

        Raises:
            PromptNotFoundError: 프롬프트를 찾을 수 없음
        """
        async with self.db_manager.get_session() as session:
            # 프롬프트 조회
            result = await session.execute(select(PromptModel).where(PromptModel.id == prompt_id))
            prompt = result.scalar_one_or_none()

            if not prompt:
                raise PromptNotFoundError(prompt_id)

            await session.delete(prompt)
            await session.commit()

            logger.info(
                "✅ 프롬프트 삭제 완료",
                prompt_id=prompt_id,
                name=prompt.name,
            )

            return True

    async def get_active_prompts(
        self, category: str | None = None
    ) -> builtins.list[PromptResponse]:
        """
        활성화된 프롬프트 목록 조회

        Args:
            category: 카테고리 필터 (선택적)

        Returns:
            활성 프롬프트 목록
        """
        result = await self.list(is_active=True, category=category, per_page=1000)
        return result.prompts
