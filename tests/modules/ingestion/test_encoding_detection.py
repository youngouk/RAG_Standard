"""인코딩 자동 감지 테스트"""
import tempfile
from pathlib import Path

from app.modules.ingestion.connectors.encoding import detect_file_encoding


class TestEncodingDetection:
    """파일 인코딩 자동 감지 테스트"""

    def test_detect_utf8_encoding(self):
        """UTF-8 파일 감지"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("이름,전화번호\n홍길동,010-1234-5678\n")
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            assert encoding.lower() in ['utf-8', 'utf8', 'ascii']
        finally:
            temp_path.unlink()

    def test_detect_euc_kr_encoding(self):
        """EUC-KR 파일 감지"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='euc-kr', delete=False, suffix='.csv') as f:
            f.write("이름,나이\n김철수,30\n")
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            assert encoding.lower() in ['euc-kr', 'cp949']
        finally:
            temp_path.unlink()

    def test_detect_large_file_sampling(self):
        """대용량 파일은 샘플링"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            # 1MB 파일 생성
            for i in range(10000):
                f.write(f"row{i},data{i},value{i}\n")
            temp_path = Path(f.name)

        try:
            # 100KB만 샘플링하므로 빠름
            encoding = detect_file_encoding(temp_path, sample_size=100_000)
            assert encoding is not None
        finally:
            temp_path.unlink()

    def test_fallback_to_utf8_on_error(self):
        """감지 실패 시 UTF-8 fallback"""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'\x00\x01\x02\x03')  # 바이너리 파일
            temp_path = Path(f.name)

        try:
            encoding = detect_file_encoding(temp_path)
            # chardet이 감지한 인코딩 또는 UTF-8 fallback
            # 바이너리 파일은 ascii로 감지될 수 있음
            assert encoding.lower() in ['utf-8', 'ascii']
        finally:
            temp_path.unlink()
