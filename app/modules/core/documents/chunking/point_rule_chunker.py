"""
Point Rule Chunker - 포인트 규정 전용 청킹 전략

포인트 규정 Excel 파일의 각 항목을 개별 청크로 변환합니다.
HTML 형식의 상세 규정을 파싱하여 마크다운 형식으로 정리합니다.

처리 흐름:
1. 각 행(항목)을 개별 청크로 변환
2. HTML 콘텐츠를 규정/신청방법/FAQ로 파싱
3. 구조화된 마크다운 형식으로 포맷팅
4. 숫자형 메타데이터 추출 (point_amount 등)

사용 예시:
    >>> chunker = PointRuleChunker()
    >>> document = Document(
    ...     source='포인트 규정.xlsx',
    ...     doc_type='POINT_RULE',
    ...     data=[{'주제': '소개포인트', '항목명': '소개받아 가입', ...}]
    ... )
    >>> chunks = chunker.chunk(document)
    >>> len(chunks)
    83
"""

import re
from html.parser import HTMLParser
from typing import Any

import pandas as pd

from app.lib.logger import get_logger

from ..models import Chunk, Document
from .base import BaseChunker

logger = get_logger(__name__)


class HTMLTextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출하는 간단한 파서"""

    def __init__(self) -> None:
        super().__init__()
        self.result: list[str] = []
        self.current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.current_tag = tag
        # 리스트 아이템 앞에 불릿 추가
        if tag == "li":
            self.result.append("\n- ")
        # 제목 앞에 마크다운 헤더 추가
        elif tag == "h4":
            self.result.append("\n### ")
        # 줄바꿈 처리
        elif tag == "br":
            self.result.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ["h4", "p", "div"]:
            self.result.append("\n")
        self.current_tag = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.result.append(text)

    def get_text(self) -> str:
        return "".join(self.result).strip()


class PointRuleChunker(BaseChunker):
    """
    포인트 규정 전용 청킹 전략: 1개 항목 = 1개 청크

    포인트 규정과 같이 구조화된 테이블 데이터에 적합합니다.
    각 항목을 개별 청크로 변환하며, HTML 상세 규정을 파싱합니다.

    Attributes:
        parse_html: HTML 콘텐츠 파싱 여부 (기본: True)

    사용 예시:
        >>> chunker = PointRuleChunker()
        >>> chunks = chunker.chunk(document)
        >>> chunks[0].metadata['point_amount']
        30000
    """

    def __init__(self, parse_html: bool = True):
        """
        PointRuleChunker 초기화

        Args:
            parse_html: HTML 콘텐츠를 파싱할지 여부 (기본: True)
        """
        self.parse_html = parse_html
        logger.debug(f"PointRuleChunker initialized (parse_html={parse_html})")

    def chunk(self, document: Document) -> list[Chunk]:
        """
        문서를 항목별로 청크 분할

        Args:
            document: 분할할 문서 (포인트 규정 형식)

        Returns:
            Chunk 객체 리스트

        Raises:
            ValueError: 잘못된 문서 형식
        """
        self.validate_document(document)

        # 데이터는 리스트 형태여야 함
        if not isinstance(document.data, list):
            raise ValueError(f"PointRuleChunker requires list data, got {type(document.data)}")

        logger.info(f"Chunking {len(document.data)} point rule items")

        chunks = []
        for idx, item in enumerate(document.data):
            try:
                chunk = self._create_chunk_from_item(item, idx, document)
                if chunk:  # 유효한 청크만 추가
                    chunks.append(chunk)
            except Exception as e:
                logger.warning(f"Failed to create chunk from item {idx}: {e}")
                continue

        chunks = self.post_process_chunks(chunks)

        logger.info(f"Created {len(chunks)} chunks from {len(document.data)} items")
        return chunks

    def _create_chunk_from_item(self, item: dict, index: int, document: Document) -> Chunk | None:
        """
        개별 항목에서 청크 생성

        Args:
            item: 포인트 규정 항목 (딕셔너리)
            index: 항목 인덱스
            document: 원본 문서

        Returns:
            Chunk 객체 또는 None (건너뛸 항목)
        """
        # 필수 필드 추출
        category = item.get("주제", "")
        item_name = item.get("항목명", "")

        # 항목명이 없으면 건너뜀
        if not item_name:
            logger.debug(f"Skipping item {index}: no item_name")
            return None

        # 포인트 금액 추출 (숫자형 변환)
        point_amount = self._extract_number(item.get("포인트적립액"))
        vip_point_amount = self._extract_number(item.get("우수포인트 적립액"))

        # 기타 필드
        frequency = item.get("횟수", "")
        post_location = item.get("후기게시 위치", "")
        board_url = item.get("게시판 URL", "")
        html_content = item.get("상세 적립규정", "")

        # 콘텐츠 생성 (마크다운 형식)
        content = self._format_content(
            category=category,
            item_name=item_name,
            point_amount=point_amount,
            vip_point_amount=vip_point_amount,
            frequency=frequency,
            post_location=post_location,
            board_url=board_url,
            html_content=html_content,
        )

        # 메타데이터 생성
        metadata = {
            "doc_type": document.doc_type,
            "source_file": str(document.source),
            "original_index": index,
            "category": category,
            "item_name": item_name,
            "point_amount": point_amount,
            "vip_point_amount": vip_point_amount,
            "frequency": frequency,
            "has_detail": bool(html_content),
        }

        # 문서 레벨 메타데이터 병합
        metadata.update(document.metadata)

        return Chunk(content=content, metadata=metadata, chunk_index=index)

    def _extract_number(self, value: Any) -> int | None:
        """
        값에서 숫자 추출

        Args:
            value: 추출할 값 (int, float, str 등)

        Returns:
            정수 또는 None
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None

        if isinstance(value, int | float):
            return int(value)

        # 문자열에서 숫자만 추출
        if isinstance(value, str):
            numbers = re.findall(r"\d+", value.replace(",", ""))
            if numbers:
                return int(numbers[0])

        return None

    def _format_content(
        self,
        category: str,
        item_name: str,
        point_amount: int | None,
        vip_point_amount: int | None,
        frequency: str,
        post_location: str,
        board_url: str,
        html_content: str,
    ) -> str:
        """
        청크 콘텐츠를 마크다운 형식으로 포맷팅

        Args:
            category: 주제 (예: 소개포인트)
            item_name: 항목명 (예: 소개받아 가입)
            point_amount: 적립 포인트
            vip_point_amount: 우수회원 적립 포인트
            frequency: 적립 횟수
            post_location: 후기 게시 위치
            board_url: 게시판 URL
            html_content: HTML 형식의 상세 규정

        Returns:
            마크다운 포맷팅된 콘텐츠
        """
        parts = []

        # 제목
        parts.append(f"## {item_name}")
        if category:
            parts.append(f"**카테고리**: {category}")

        # 포인트 정보
        if point_amount:
            parts.append(f"**적립 포인트**: {point_amount:,}점")
        if vip_point_amount:
            parts.append(f"**우수회원 적립**: {vip_point_amount:,}점")
        if frequency:
            parts.append(f"**적립 횟수**: {frequency}")

        # 추가 정보
        if post_location and not pd.isna(post_location):
            parts.append(f"**후기 게시 위치**: {post_location}")
        if board_url and not pd.isna(board_url):
            parts.append(f"**게시판**: {board_url}")

        # HTML 상세 규정 파싱
        if html_content and self.parse_html:
            parsed = self._parse_html_content(html_content)
            if parsed:
                parts.append("")  # 빈 줄
                parts.append(parsed)

        return "\n".join(parts)

    def _parse_html_content(self, html_content: str) -> str:
        """
        HTML 콘텐츠를 마크다운 텍스트로 변환

        Args:
            html_content: HTML 형식의 상세 규정

        Returns:
            마크다운 형식의 텍스트
        """
        if not html_content or pd.isna(html_content):
            return ""

        try:
            parser = HTMLTextExtractor()
            parser.feed(html_content)
            text = parser.get_text()

            # 연속된 줄바꿈 정리
            text = re.sub(r"\n{3,}", "\n\n", text)

            # "1. 규정", "2. 신청방법", "3. 자주 묻는 질문" 헤더 정리
            text = re.sub(r"### (\d+)\. ", r"### ", text)

            return text.strip()

        except Exception as e:
            logger.warning(f"HTML parsing failed: {e}")
            # 폴백: 태그만 제거
            return re.sub(r"<[^>]+>", "", html_content).strip()

    def validate_document(self, document: Document) -> None:
        """
        문서 검증 (포인트 규정 형식 체크)

        Args:
            document: 검증할 문서

        Raises:
            ValueError: 잘못된 문서 형식
        """
        super().validate_document(document)

        if not isinstance(document.data, list):
            raise ValueError("Point rule document must have list data")

        if len(document.data) == 0:
            raise ValueError("Point rule document cannot be empty")

        # 첫 번째 항목으로 필드 검증
        first_item = document.data[0]
        if not isinstance(first_item, dict):
            raise ValueError("Point rule items must be dictionaries")

        # 필수 필드 확인 (유연하게 처리)
        required_fields = ["항목명"]  # 최소 필수
        for field in required_fields:
            if field not in first_item:
                logger.warning(f"Required field '{field}' not found in first item")
