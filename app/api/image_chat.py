"""
Image Chat API endpoints
이미지와 텍스트를 함께 처리하는 멀티모달 채팅 API

최신 Gemini API (google-generativeai)를 활용한 이미지 분석 및 질의응답 기능 제공
"""

import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field

from ..lib.llm_client import get_llm_factory
from ..lib.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Image Chat"])


class ImageChatResponse(BaseModel):
    """이미지 채팅 응답 모델"""

    message: str = Field(..., description="생성된 응답 메시지")
    provider: str = Field(..., description="사용된 LLM 제공자 (google, openai, anthropic)")
    image_count: int = Field(..., description="처리된 이미지 개수")
    timestamp: str = Field(..., description="응답 생성 시각 (ISO 8601)")


# 지원하는 이미지 MIME 타입
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}

# 최대 이미지 크기 (20MB - Gemini API 권장 기준)
MAX_IMAGE_SIZE = 20 * 1024 * 1024


def validate_image(file: UploadFile) -> dict[str, Any]:
    """
    이미지 파일 검증

    Args:
        file: 업로드된 파일 객체

    Returns:
        검증 결과 딕셔너리 (valid, mime_type, error)
    """
    # MIME 타입 검증
    if file.content_type not in SUPPORTED_IMAGE_TYPES:
        return {
            "valid": False,
            "error": (
                f"지원하지 않는 이미지 형식입니다: {file.content_type}. "
                f"지원 형식: {', '.join(SUPPORTED_IMAGE_TYPES.keys())}"
            ),
        }

    # 파일 크기 검증
    if file.size and file.size > MAX_IMAGE_SIZE:
        size_mb = file.size / (1024 * 1024)
        max_mb = MAX_IMAGE_SIZE / (1024 * 1024)
        return {
            "valid": False,
            "error": f"이미지 크기가 너무 큽니다: {size_mb:.1f}MB. 최대: {max_mb}MB",
        }

    return {"valid": True, "mime_type": file.content_type}


async def validate_image_content(image_bytes: bytes) -> bool:
    """
    이미지 내용 검증 (PIL을 사용하여 유효한 이미지인지 확인)

    Args:
        image_bytes: 이미지 바이트 데이터

    Returns:
        유효한 이미지 여부
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()  # 이미지 무결성 검증
        return True
    except Exception as e:
        logger.error(f"이미지 검증 실패: {e}")
        return False


@router.post("/image-chat", response_model=ImageChatResponse)
async def chat_with_images(
    prompt: str = Form(..., description="사용자 질문 또는 지시사항"),
    images: list[UploadFile] = File(..., description="분석할 이미지 파일 (최대 3,600개)"),
    system_prompt: str | None = Form(None, description="시스템 프롬프트 (선택사항)"),
    provider: str | None = Form(None, description="사용할 LLM 제공자 (google, openai, anthropic)"),
):
    """
    이미지와 텍스트를 함께 처리하는 멀티모달 채팅 API

    ### 기능
    - 이미지 기반 질의응답 (Visual Question Answering)
    - 이미지 분류 및 캡셔닝
    - 객체 탐지 및 설명
    - 여러 이미지 동시 분석

    ### 지원 형식
    - JPEG, PNG, WebP, HEIC, HEIF
    - 최대 이미지 크기: 20MB
    - 최대 이미지 개수: 3,600개 (Gemini 2.5 기준)

    ### 예시
    ```bash
    curl -X POST "http://localhost:8000/image-chat" \\
      -F "prompt=이 이미지에 무엇이 보이나요?" \\
      -F "images=@photo.jpg" \\
      -F "provider=google"
    ```
    """
    try:
        # 1. 이미지 개수 제한 확인 (Gemini 2.5 Pro/Flash 기준)
        if len(images) > 3600:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "이미지 개수 제한 초과",
                    "message": f"제공된 이미지 개수가 제한을 초과합니다 ({len(images)}개)",
                    "suggestion": "이미지 개수를 줄이거나 여러 번 나누어 요청하세요",
                    "current_count": len(images),
                    "max_count": 3600,
                },
            )

        # 2. 각 이미지 검증 및 바이트 데이터 수집
        image_bytes_list: list[bytes] = []
        mime_types_list: list[str] = []

        for idx, image_file in enumerate(images):
            # 파일 검증
            validation = validate_image(image_file)
            if not validation["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "이미지 검증 실패",
                        "message": f"{idx + 1}번째 이미지를 검증할 수 없습니다",
                        "suggestion": "이미지 형식(JPEG, PNG, WebP, HEIC, HEIF)과 크기(최대 20MB)를 확인하세요",
                        "image_index": idx + 1,
                        "validation_error": validation["error"],
                        "supported_formats": list(SUPPORTED_IMAGE_TYPES.keys()),
                        "max_size_mb": MAX_IMAGE_SIZE / (1024 * 1024),
                    },
                )

            # 이미지 바이트 읽기
            image_bytes = await image_file.read()

            # 내용 검증 (유효한 이미지인지 확인)
            if not await validate_image_content(image_bytes):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "이미지 내용 검증 실패",
                        "message": f"{idx + 1}번째 이미지의 내용이 손상되었거나 유효하지 않습니다",
                        "suggestion": "다른 이미지를 사용하거나 파일 무결성을 확인하세요",
                        "image_index": idx + 1,
                        "possible_causes": [
                            "파일이 손상됨",
                            "불완전한 다운로드",
                            "지원하지 않는 이미지 형식",
                        ],
                    },
                )

            image_bytes_list.append(image_bytes)
            mime_types_list.append(validation["mime_type"])

            logger.info(
                f"이미지 {idx + 1}/{len(images)} 검증 완료: "
                f"크기={len(image_bytes)} bytes, MIME={validation['mime_type']}"
            )

        # 3. LLM Factory 가져오기
        llm_factory = get_llm_factory()

        # 4. Provider 결정 (기본값: google)
        # 멀티모달은 현재 Google Gemini만 지원
        if provider and provider != "google":
            logger.warning(
                f"요청된 Provider '{provider}'는 멀티모달을 지원하지 않습니다. "
                "Google Gemini를 사용합니다."
            )
        provider = "google"

        # 5. Gemini 클라이언트로 멀티모달 생성
        client = llm_factory.get_client(provider=provider)

        # 6. Multimodal 지원 여부 확인
        if not hasattr(client, "generate_multimodal"):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "이미지 분석 서비스 사용 불가",
                    "message": "이미지를 분석할 수 있는 AI 모델이 현재 사용 불가합니다",
                    "suggestion": ".env 파일에 GOOGLE_API_KEY(Gemini) 또는 OPENAI_API_KEY(GPT-4V)를 설정하세요",
                    "required_keys": ["GOOGLE_API_KEY", "OPENAI_API_KEY"],
                    "docs": "https://github.com/youngouk/RAG_Standard#multimodal-setup",
                },
            )

        logger.info(
            f"멀티모달 요청 시작: provider={provider}, "
            f"이미지={len(image_bytes_list)}개, 프롬프트={prompt[:50]}..."
        )

        response_text = await client.generate_multimodal(
            prompt=prompt,
            images=image_bytes_list,
            mime_types=mime_types_list,
            system_prompt=system_prompt,
        )

        logger.info(
            f"멀티모달 응답 생성 완료: provider={provider}, " f"응답 길이={len(response_text)}"
        )

        return ImageChatResponse(
            message=response_text,
            provider=provider,
            image_count=len(images),
            timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        # FastAPI HTTPException은 그대로 전파
        raise
    except Exception as e:
        logger.error(f"이미지 채팅 처리 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "이미지 처리 오류",
                "message": "이미지 처리 중 예기치 않은 오류가 발생했습니다",
                "suggestion": "이미지 크기와 형식을 확인하고 다시 시도하세요. 문제가 지속되면 관리자에게 문의하세요",
                "error_detail": str(e),
                "supported_formats": list(SUPPORTED_IMAGE_TYPES.keys()),
                "max_size_mb": MAX_IMAGE_SIZE / (1024 * 1024),
            },
        ) from e


@router.get("/image-chat/supported-formats")
async def get_supported_image_formats():
    """
    지원하는 이미지 형식 정보 조회

    Returns:
        지원 형식, 크기 제한, 개수 제한 등의 정보
    """
    return {
        "supported_formats": {
            mime_type: {"extension": ext, "description": f"{ext.upper()} images"}
            for mime_type, ext in SUPPORTED_IMAGE_TYPES.items()
        },
        "max_image_size_bytes": MAX_IMAGE_SIZE,
        "max_image_size_mb": MAX_IMAGE_SIZE / (1024 * 1024),
        "max_images_per_request": 3600,
        "supported_providers": ["google"],
        "notes": [
            "Google Gemini 2.5 Pro/Flash는 최대 3,600개 이미지 지원",
            "총 요청 크기는 20MB 이하 권장 (인라인 전송 시)",
            "더 큰 파일은 File API 사용 권장 (향후 지원 예정)",
        ],
    }
