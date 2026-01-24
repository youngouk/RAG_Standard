"""
Upload API endpoints
파일 업로드 및 문서 처리 API 엔드포인트
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..lib.auth import get_api_key
from ..lib.logger import get_logger
from ..modules.core.privacy.masker import DEFAULT_WHITELIST, PrivacyMasker

logger = get_logger(__name__)

# PII 마스킹을 위한 인스턴스 (privacy.enabled 체크 후 초기화)
# DEFAULT_WHITELIST 사용 (오탐 방지: 이모님, 헬퍼님, 담당 등)
# Note: DI Container 외부에서 사용하므로 기본 화이트리스트 직접 지정
_privacy_masker: PrivacyMasker | None = PrivacyMasker(whitelist=list(DEFAULT_WHITELIST))
# ✅ H4 보안 패치: Upload API 인증 추가
# 파일 업로드/삭제는 시스템 변경이므로 인증 필요
router = APIRouter(tags=["Upload"], dependencies=[Depends(get_api_key)])
modules: dict[str, Any] = {}
config: dict[str, Any] = {}


def set_dependencies(app_modules: dict[str, Any], app_config: dict[str, Any]):
    """의존성 주입"""
    global modules, config, _privacy_masker
    modules = app_modules
    config = app_config

    # privacy.enabled: false → PII 마스킹 비활성화
    privacy_config = config.get("privacy", {})
    if not privacy_config.get("enabled", True):
        _privacy_masker = None
        logger.info("🔓 Upload API: PII 마스킹 비활성화됨 (privacy.enabled: false)")


JOBS_FILE = Path("/app/uploads/jobs.json")


def load_upload_jobs() -> dict[str, dict[str, Any]]:
    """업로드 작업 상태를 파일에서 로드"""
    try:
        if JOBS_FILE.exists():
            with open(JOBS_FILE, encoding="utf-8") as f:
                loaded_data = json.load(f)
                return dict(loaded_data) if isinstance(loaded_data, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to load jobs file: {e}")
    return {}


def save_upload_jobs(jobs: dict[str, dict[str, Any]]):
    """업로드 작업 상태를 파일에 저장"""
    try:
        JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save jobs file: {e}")


upload_jobs: dict[str, dict[str, Any]] = load_upload_jobs()


class DocumentInfo(BaseModel):
    """문서 정보 모델"""

    id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: str
    status: str
    chunk_count: int | None = None
    processing_time: float | None = None
    error_message: str | None = None


class UploadResponse(BaseModel):
    """업로드 응답 모델"""

    job_id: str
    message: str
    filename: str
    file_size: int
    estimated_processing_time: float
    timestamp: str


class JobStatusResponse(BaseModel):
    """작업 상태 응답 모델"""

    job_id: str
    status: str
    progress: float
    message: str
    filename: str
    chunk_count: int | None = None
    processing_time: float | None = None
    error_message: str | None = None
    timestamp: str


class DocumentListResponse(BaseModel):
    """문서 목록 응답 모델"""

    documents: list[DocumentInfo]
    total_count: int
    page: int
    page_size: int
    has_next: bool


class BulkDeleteRequest(BaseModel):
    """벌크 삭제 요청 모델"""

    ids: list[str] = Field(..., description="삭제할 문서 ID 목록")


class BulkDeleteResponse(BaseModel):
    """벌크 삭제 응답 모델"""

    deleted_count: int
    failed_count: int
    failed_ids: list[str] = []
    message: str
    timestamp: str


def get_upload_directory() -> Path:
    """업로드 디렉토리 반환"""
    upload_path = config.get("uploads", {}).get("directory", "./uploads")
    upload_dir = Path(upload_path).resolve()
    try:
        upload_dir.mkdir(exist_ok=True, parents=True)
        temp_dir = upload_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
    except PermissionError:
        upload_dir = Path("/app/uploads")
        upload_dir.mkdir(exist_ok=True, parents=True)
        temp_dir = upload_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
    return upload_dir


def estimate_processing_time(file_size: int, file_type: str) -> float:
    """파일 크기와 타입을 기반으로 처리 시간 예측"""
    base_time = 20.0
    size_mb = file_size / (1024 * 1024)
    processing_rates = {
        "pdf": 15.0,
        "docx": 10.0,
        "xlsx": 20.0,
        "txt": 3.0,
        "md": 3.0,
        "html": 8.0,
        "csv": 12.0,
        "json": 5.0,
    }
    ext = file_type.lower()
    rate = processing_rates.get(ext, 10.0)
    estimated_time = base_time + size_mb * rate
    if size_mb > 10:
        extra_penalty = (size_mb - 10) * 3
        estimated_time += extra_penalty
    return max(30.0, min(estimated_time, 1800.0))


def validate_file(file: UploadFile) -> dict[str, Any]:
    """파일 검증"""
    supported_types = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/csv": "csv",
        "text/html": "html",
        "text/markdown": "md",
        "application/json": "json",
    }
    if file.content_type not in supported_types:
        ext = Path(file.filename or "unknown").suffix.lower()[1:]
        if ext not in supported_types.values():
            return {
                "valid": False,
                "error": {
                    "error": "지원하지 않는 파일 형식",
                    "message": f"'{file.content_type}' 형식은 지원되지 않습니다",
                    "suggestion": "지원 형식: PDF, DOCX, TXT, MD, CSV, XLSX, HTML, JSON",
                    "file_name": file.filename,
                    "file_type": file.content_type,
                    "supported_extensions": [".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".html", ".json"],
                },
            }
        file_type = ext
    else:
        file_type = supported_types[file.content_type]
    max_size = config.get("uploads", {}).get("max_file_size", 50 * 1024 * 1024)
    if file.size and file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        file_size_mb = file.size / (1024 * 1024)
        return {
            "valid": False,
            "error": {
                "error": "파일 크기 초과",
                "message": f"파일 크기({file_size_mb:.1f}MB)가 최대 허용 크기({max_size_mb:.0f}MB)를 초과했습니다",
                "suggestion": "파일을 압축하거나 여러 파일로 분할하여 업로드하세요",
                "file_name": file.filename,
                "file_size_mb": round(file_size_mb, 1),
                "max_size_mb": int(max_size_mb),
            },
        }
    return {"valid": True, "file_type": file_type}


async def process_document_background(job_id: str, file_path: Path, filename: str, file_type: str):
    """백그라운드 문서 처리"""
    try:
        upload_jobs[job_id].update(
            {"status": "processing", "progress": 10, "message": "문서 처리 시작..."}
        )
        save_upload_jobs(upload_jobs)
        document_processor = modules.get("document_processor")
        retrieval_module = modules.get("retrieval")
        if not document_processor or not retrieval_module:
            raise Exception("Required modules not available")
        logger.info(f"Loading document: {filename}")
        upload_jobs[job_id].update({"progress": 30, "message": "문서 로딩 중..."})
        save_upload_jobs(upload_jobs)
        file_size = file_path.stat().st_size

        # PII 마스킹: 파일명에서 개인정보 마스킹 (활성화 시에만)
        # 예: "홍길동 고객님.txt" → "고객_고객님.txt"
        if _privacy_masker:
            masked_filename = _privacy_masker.mask_filename(filename)
            if masked_filename != filename:
                logger.info(f"파일명 PII 마스킹 적용: {filename} → {masked_filename}")
        else:
            masked_filename = filename  # PII 마스킹 비활성화 시 원본 사용

        docs = await document_processor.load_document(
            str(file_path),
            {
                "source_file": masked_filename,
                "file_type": file_type,
                "original_file_size": file_size,
            },
        )
        logger.info(f"Splitting document into chunks: {len(docs)} documents")
        upload_jobs[job_id].update({"progress": 50, "message": "문서 분할 중..."})
        save_upload_jobs(upload_jobs)
        chunks = await document_processor.split_documents(docs)
        logger.info(f"Document split into {len(chunks)} chunks")
        upload_jobs[job_id].update(
            {"progress": 70, "message": f"임베딩 생성 중... ({len(chunks)}개 청크)"}
        )
        save_upload_jobs(upload_jobs)
        embedded_chunks = await document_processor.embed_chunks(chunks)
        upload_jobs[job_id].update(
            {"progress": 90, "message": f"벡터 DB에 저장 중... ({len(embedded_chunks)}개 임베딩)"}
        )
        save_upload_jobs(upload_jobs)
        await retrieval_module.add_documents(embedded_chunks)
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")
        processing_time = datetime.now().timestamp() - upload_jobs[job_id]["start_time"]
        upload_jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "문서 처리 완료",
                "chunk_count": len(chunks),
                "processing_time": processing_time,
            }
        )
        save_upload_jobs(upload_jobs)
        logger.info(
            f"Document processing completed: {filename}, {len(chunks)} chunks, {processing_time:.2f}s"
        )
    except Exception as error:
        logger.error(f"Document processing failed: {error}")
        upload_jobs[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": "문서 처리 실패",
                "error_message": str(error),
            }
        )
        save_upload_jobs(upload_jobs)
        try:
            if file_path.exists():
                os.unlink(file_path)
        except Exception:
            pass


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata: str | None = Form(None),
):
    """문서 업로드"""
    try:
        validation = validate_file(file)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["error"])
        file_type = validation["file_type"]
        job_id = str(uuid4())
        upload_dir = get_upload_directory()
        temp_dir = upload_dir / "temp"
        safe_filename = Path(file.filename or "unknown").name
        if not safe_filename or safe_filename.startswith("."):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "잘못된 파일명",
                    "message": "파일명이 유효하지 않습니다",
                    "suggestion": "올바른 파일명을 사용하여 다시 업로드하세요 (숨김 파일은 업로드할 수 없습니다)",
                    "file_name": file.filename,
                },
            )
        file_path = temp_dir / f"{job_id}_{safe_filename}"
        try:
            resolved_path = file_path.resolve()
            resolved_temp_dir = temp_dir.resolve()
            if not str(resolved_path).startswith(str(resolved_temp_dir)):
                logger.error(f"Path Traversal 시도 차단: {file.filename}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "보안 검증 실패",
                        "message": "파일 경로에서 보안 위협이 감지되었습니다",
                        "suggestion": "파일명에 특수문자나 경로 문자(.., /)가 포함되지 않았는지 확인하세요",
                        "file_name": file.filename,
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"파일 경로 검증 실패: {e}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "파일 경로 검증 실패",
                    "message": "파일 경로를 검증하는 중 오류가 발생했습니다",
                    "suggestion": "파일명에 특수문자가 포함되지 않았는지 확인하고 다시 시도하세요",
                    "file_name": file.filename,
                    "technical_error": str(e),
                },
            ) from e
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        file_size = len(content)
        filename = file.filename or "unknown"
        upload_jobs[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "status": "pending",
            "progress": 0,
            "message": "업로드 완료, 처리 대기 중...",
            "start_time": datetime.now().timestamp(),
            "chunk_count": None,
            "processing_time": None,
            "error_message": None,
        }
        save_upload_jobs(upload_jobs)
        background_tasks.add_task(
            process_document_background, job_id, file_path, filename, file_type
        )
        estimated_time = estimate_processing_time(file_size, file_type)
        logger.info(f"Document upload initiated: {file.filename}, job_id: {job_id}")
        size_mb = file_size / (1024 * 1024)
        if estimated_time > 60:
            time_msg = f"약 {estimated_time / 60:.1f}분"
        else:
            time_msg = f"약 {estimated_time:.0f}초"
        if size_mb > 10:
            warning_msg = (
                " ⚠️ 대용량 파일로 인해 처리 시간이 오래 걸릴 수 있습니다. 브라우저를 닫지 마세요."
            )
        else:
            warning_msg = ""
        user_message = f"파일 업로드 완료! 문서 처리 중입니다. 예상 시간: {time_msg} (파일 크기: {size_mb:.1f}MB){warning_msg}"
        return UploadResponse(
            job_id=job_id,
            message=user_message,
            filename=filename,
            file_size=file_size,
            estimated_processing_time=estimated_time,
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Upload error: {error}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "업로드 실패",
                "message": "파일 업로드 중 오류가 발생했습니다",
                "suggestion": "네트워크 연결을 확인하고 다시 시도하세요. 문제가 지속되면 관리자에게 문의하세요",
                "file_name": file.filename if file and hasattr(file, "filename") else None,
                "retry_after": 30,
                "technical_error": str(error),
            },
        ) from error


@router.get("/upload/status/{job_id}", response_model=JobStatusResponse)
async def get_upload_status(job_id: str):
    """업로드 작업 상태 조회"""
    global upload_jobs
    if job_id not in upload_jobs:
        logger.info(f"Job {job_id} not found in memory, reloading from file")
        upload_jobs = load_upload_jobs()
        if job_id not in upload_jobs:
            logger.warning(f"Job {job_id} not found even after reload")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "작업을 찾을 수 없음",
                    "message": "요청하신 업로드 작업을 찾을 수 없습니다",
                    "suggestion": "서버가 재시작되었을 수 있습니다. 파일을 다시 업로드해주세요",
                    "job_id": job_id,
                    "retry_upload": True,
                },
            )
    job = upload_jobs[job_id]
    current_processing_time = None
    if job["status"] == "processing":
        current_processing_time = datetime.now().timestamp() - job["start_time"]
    logger.info(f"Job {job_id} status: {job['status']}, progress: {job['progress']}%")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        filename=job["filename"],
        chunk_count=job["chunk_count"],
        processing_time=job["processing_time"] or current_processing_time,
        error_message=job["error_message"],
        timestamp=datetime.now().isoformat(),
    )


@router.get("/upload/documents", response_model=DocumentListResponse)
async def list_documents(page: int = 1, page_size: int = 20):
    """문서 목록 조회"""
    try:
        retrieval_module = modules.get("retrieval")
        if not retrieval_module:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "시스템 모듈 사용 불가",
                    "message": "문서 검색 모듈을 사용할 수 없습니다",
                    "suggestion": "서버 상태를 확인하고 관리자에게 문의하세요",
                    "module_name": "retrieval",
                    "retry_after": 60,
                },
            )
        logger.info(f"Listing documents: page={page}, page_size={page_size}")
        documents_data = await retrieval_module.list_documents(page=page, page_size=page_size)
        logger.info(f"Retrieved documents_data: {documents_data}")
        documents = []
        for doc_data in documents_data.get("documents", []):
            upload_date = doc_data.get("upload_date", 0)
            if isinstance(upload_date, int | float) and upload_date > 0:
                upload_date = datetime.fromtimestamp(upload_date).isoformat()
            else:
                upload_date = datetime.now().isoformat()
            documents.append(
                DocumentInfo(
                    id=doc_data.get("id", "unknown"),
                    filename=doc_data.get("filename", "unknown"),
                    file_type=doc_data.get("file_type", "unknown"),
                    file_size=doc_data.get("file_size", 0),
                    upload_date=upload_date,
                    status="completed",
                    chunk_count=doc_data.get("chunk_count", 0),
                )
            )
        total_count = documents_data.get("total_count", len(documents))
        response = DocumentListResponse(
            documents=documents,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total_count,
        )
        logger.info(f"Returning response: {len(documents)} documents, total={total_count}")
        return response
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"List documents error: {error}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "문서 목록 조회 실패",
                "message": "문서 목록을 불러오는 중 오류가 발생했습니다",
                "suggestion": "잠시 후 다시 시도하거나 관리자에게 문의하세요",
                "page": page,
                "page_size": page_size,
                "retry_after": 30,
                "technical_error": str(error),
            },
        ) from error


@router.delete("/upload/documents/{document_id}")
async def delete_document(document_id: str):
    """문서 삭제"""
    try:
        retrieval_module = modules.get("retrieval")
        if not retrieval_module:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "시스템 모듈 사용 불가",
                    "message": "문서 검색 모듈을 사용할 수 없습니다",
                    "suggestion": "서버 상태를 확인하고 관리자에게 문의하세요",
                    "module_name": "retrieval",
                    "retry_after": 60,
                },
            )
        await retrieval_module.delete_document(document_id)
        logger.info(f"Document deleted: {document_id}")
        return {
            "message": "Document deleted successfully",
            "document_id": document_id,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Delete document error: {error}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "문서 삭제 실패",
                "message": "문서를 삭제하는 중 오류가 발생했습니다",
                "suggestion": "문서가 이미 삭제되었거나 접근 권한이 없을 수 있습니다. 다시 시도하거나 관리자에게 문의하세요",
                "document_id": document_id,
                "retry_after": 30,
                "technical_error": str(error),
            },
        ) from error


@router.post("/upload/documents/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_documents(request: BulkDeleteRequest):
    """문서 일괄 삭제"""
    try:
        retrieval_module = modules.get("retrieval")
        if not retrieval_module:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "시스템 모듈 사용 불가",
                    "message": "문서 검색 모듈을 사용할 수 없습니다",
                    "suggestion": "서버 상태를 확인하고 관리자에게 문의하세요",
                    "module_name": "retrieval",
                    "retry_after": 60,
                },
            )
        deleted_count = 0
        failed_count = 0
        failed_ids = []
        logger.info(f"Bulk delete requested for {len(request.ids)} documents: {request.ids}")
        for document_id in request.ids:
            try:
                if not document_id or document_id.strip() == "":
                    logger.warning(f"Skipping invalid document ID: {document_id}")
                    failed_count += 1
                    failed_ids.append(document_id)
                    continue
                await retrieval_module.delete_document(document_id)
                deleted_count += 1
                logger.info(f"Successfully deleted document: {document_id}")
            except Exception as delete_error:
                logger.error(f"Failed to delete document {document_id}: {delete_error}")
                failed_count += 1
                failed_ids.append(document_id)
        message = f"Bulk delete completed: {deleted_count} deleted, {failed_count} failed"
        logger.info(message)
        return BulkDeleteResponse(
            deleted_count=deleted_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            message=message,
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Bulk delete error: {error}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "일괄 삭제 실패",
                "message": "문서 일괄 삭제 중 오류가 발생했습니다",
                "suggestion": "네트워크 연결을 확인하고 다시 시도하거나 관리자에게 문의하세요",
                "requested_count": len(request.ids) if request and hasattr(request, "ids") else 0,
                "retry_after": 30,
                "technical_error": str(error),
            },
        ) from error


@router.get("/upload/supported-types")
async def get_supported_types():
    """지원하는 파일 타입 목록"""
    return {
        "supported_types": {
            "pdf": {
                "mime_type": "application/pdf",
                "description": "PDF documents",
                "max_size_mb": 10,
            },
            "docx": {
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "description": "Microsoft Word documents",
                "max_size_mb": 10,
            },
            "xlsx": {
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "description": "Microsoft Excel spreadsheets",
                "max_size_mb": 10,
            },
            "txt": {
                "mime_type": "text/plain",
                "description": "Plain text files",
                "max_size_mb": 10,
            },
            "csv": {
                "mime_type": "text/csv",
                "description": "Comma-separated values",
                "max_size_mb": 10,
            },
            "html": {"mime_type": "text/html", "description": "HTML documents", "max_size_mb": 10},
            "md": {
                "mime_type": "text/markdown",
                "description": "Markdown documents",
                "max_size_mb": 10,
            },
            "json": {
                "mime_type": "application/json",
                "description": "JSON documents",
                "max_size_mb": 10,
            },
        },
        "max_file_size": config.get("uploads", {}).get("max_file_size", 50 * 1024 * 1024),
        "max_files_per_request": 1,
    }
