"""
파일 인코딩 자동 감지 모듈

chardet 라이브러리를 사용하여 CSV/XLSX/TXT 파일의 인코딩을 자동 감지합니다.

구현일: 2026-01-08
이슈: QA-001
"""
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any

import chardet
import pandas as pd

logger = logging.getLogger(__name__)


def detect_file_encoding(
    file_path: Path,
    sample_size: int = 100_000,
) -> str:
    """
    파일 인코딩 자동 감지

    파일의 일부(기본 100KB)를 읽어 인코딩을 감지합니다.
    대용량 파일도 빠르게 처리 가능합니다.

    Args:
        file_path: 파일 경로
        sample_size: 샘플 크기 (바이트)

    Returns:
        감지된 인코딩 (예: 'utf-8', 'euc-kr')
        감지 실패 시 'utf-8' (안전한 기본값)

    Examples:
        >>> detect_file_encoding(Path("data.csv"))
        'euc-kr'

        >>> detect_file_encoding(Path("large.csv"), sample_size=50000)
        'utf-8'
    """
    try:
        # 샘플 읽기 (전체 파일이 아님)
        with open(file_path, 'rb') as f:
            raw_data = f.read(sample_size)

        # chardet으로 인코딩 감지
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']

        if encoding is None:
            logger.warning(
                f"⚠️ 인코딩 감지 실패 (파일: {file_path.name}). UTF-8로 fallback."
            )
            return 'utf-8'

        logger.info(
            f"✅ 인코딩 감지: {encoding} "
            f"(신뢰도: {confidence:.2%}, 파일: {file_path.name})"
        )

        return encoding

    except Exception as e:
        logger.error(f"❌ 인코딩 감지 중 오류 (파일: {file_path.name}): {e}")
        logger.warning("UTF-8로 fallback 시도")
        return 'utf-8'


def safe_open_file(
    file_path: Path,
    mode: str = 'r',
    encoding: str | None = None,
    errors: str = 'replace',
) -> IO[Any]:
    """
    안전한 파일 열기 (인코딩 자동 감지)

    Args:
        file_path: 파일 경로
        mode: 파일 모드 ('r', 'w' 등)
        encoding: 인코딩 (None이면 자동 감지)
        errors: 디코딩 에러 처리 ('replace', 'ignore', 'strict')

    Returns:
        파일 객체

    Examples:
        >>> with safe_open_file(Path("data.csv")) as f:
        ...     content = f.read()
    """
    # 읽기 모드이고 인코딩이 지정되지 않은 경우 자동 감지
    if 'r' in mode and encoding is None:
        encoding = detect_file_encoding(file_path)

    return open(file_path, mode, encoding=encoding, errors=errors)


def stream_csv_chunks(
    file_path: Path,
    chunk_size: int = 1000,
    encoding: str | None = None,
) -> Iterator[pd.DataFrame]:
    """
    CSV 파일을 청크 단위로 스트리밍

    메모리에 전체 파일을 로드하지 않고 청크 단위로 처리합니다.
    대용량 파일(수백 MB~GB)도 안전하게 처리 가능합니다.

    Args:
        file_path: CSV 파일 경로
        chunk_size: 청크 크기 (행 수)
        encoding: 인코딩 (None이면 자동 감지)

    Yields:
        pandas DataFrame 청크

    Examples:
        >>> for chunk in stream_csv_chunks(Path("large.csv"), chunk_size=1000):
        ...     process_chunk(chunk)  # 1000행씩 처리
    """
    # 인코딩 자동 감지
    if encoding is None:
        encoding = detect_file_encoding(file_path)

    logger.info(
        f"📄 CSV 스트리밍 시작: {file_path.name} "
        f"(인코딩: {encoding}, 청크: {chunk_size}행)"
    )

    try:
        # pandas의 chunksize 파라미터 사용
        for chunk_num, chunk in enumerate(
            pd.read_csv(
                file_path,
                encoding=encoding,
                chunksize=chunk_size,
                on_bad_lines='warn',  # 잘못된 행 경고
            ),
            start=1,
        ):
            logger.debug(f"  청크 {chunk_num}: {len(chunk)}행 처리")
            yield chunk

        logger.info(f"✅ CSV 스트리밍 완료: {file_path.name}")

    except UnicodeDecodeError as e:
        logger.error(
            f"❌ CSV 인코딩 오류 (파일: {file_path.name}, 인코딩: {encoding}): {e}"
        )
        logger.info("🔄 UTF-8로 재시도...")

        # UTF-8로 재시도
        for chunk in pd.read_csv(
            file_path,
            encoding='utf-8',
            chunksize=chunk_size,
            on_bad_lines='warn',
            encoding_errors='replace',  # 디코딩 오류 무시
        ):
            yield chunk

    except Exception as e:
        logger.error(f"❌ CSV 스트리밍 실패 (파일: {file_path.name}): {e}")
        raise


def stream_excel_sheets(
    file_path: Path,
    sheet_name: str | int | None = 0,
) -> Iterator[pd.DataFrame]:
    """
    Excel 파일을 시트 단위로 스트리밍

    Args:
        file_path: Excel 파일 경로
        sheet_name: 시트 이름 또는 인덱스 (None이면 모든 시트)

    Yields:
        pandas DataFrame (시트별)

    Examples:
        >>> for sheet_df in stream_excel_sheets(Path("data.xlsx")):
        ...     process_sheet(sheet_df)
    """
    logger.info(f"📊 Excel 스트리밍 시작: {file_path.name}")

    try:
        # openpyxl 엔진 사용 (.xlsx)
        if sheet_name is None:
            # 모든 시트 처리
            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
            for sheet in excel_file.sheet_names:
                logger.debug(f"  시트 '{sheet}' 처리 중...")
                df = pd.read_excel(excel_file, sheet_name=sheet)
                yield df
        else:
            # 특정 시트만 처리
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
            yield df

        logger.info(f"✅ Excel 스트리밍 완료: {file_path.name}")

    except Exception as e:
        logger.error(f"❌ Excel 스트리밍 실패 (파일: {file_path.name}): {e}")
        raise
