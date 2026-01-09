"""
Ingestion API

데이터 적재를 트리거하는 API 엔드포인트.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.core.di_container import AppContainer
from app.modules.ingestion.factory import IngestionConnectorFactory
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

class NotionIngestRequest(BaseModel):
    database_id: str
    category_name: str

class WebIngestRequest(BaseModel):
    sitemap_url: str
    category_name: str

@router.post("/web", status_code=202)
@inject
async def ingest_web(
    request: WebIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_service: IngestionService = Depends(Provide[AppContainer.ingestion_service]),
    connector_factory: IngestionConnectorFactory = Depends(Provide[AppContainer.connector_factory])
):
    """
    웹 사이트맵을 통한 데이터 적재 (비동기)
    """
    # 커넥터 생성
    connector = connector_factory.create({
        "type": "web_sitemap",
        "url": request.sitemap_url
    })

    # 백그라운드 작업 실행
    background_tasks.add_task(
        ingestion_service.ingest_from_connector,
        connector=connector,
        category_name=request.category_name
    )

    return {
        "status": "accepted",
        "message": "Web ingestion started in background",
        "target": {
            "sitemap_url": request.sitemap_url,
            "category": request.category_name
        }
    }

@router.post("/notion", status_code=202)
@inject
async def ingest_notion(
    request: NotionIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_service: IngestionService = Depends(Provide[AppContainer.ingestion_service])
):
    """
    Notion 데이터베이스 적재 작업 시작 (비동기)
    """
    if not request.database_id:
        raise HTTPException(status_code=400, detail="database_id is required")

    # 백그라운드 작업으로 스케줄링
    background_tasks.add_task(
        ingestion_service.ingest_notion_database,
        db_id=request.database_id,
        category_name=request.category_name
    )

    return {
        "status": "accepted",
        "message": "Ingestion started in background",
        "target": {
            "database_id": request.database_id,
            "category": request.category_name
        }
    }
