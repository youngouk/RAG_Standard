"""CSV 스트리밍 처리 테스트"""
import tempfile
from pathlib import Path

from app.modules.ingestion.connectors.encoding import stream_csv_chunks


class TestCSVStreaming:
    """CSV 스트리밍 처리 테스트"""

    def test_stream_small_csv(self):
        """소형 CSV 스트리밍"""
        # Given: 5행 CSV 파일
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("name,age\n")
            for i in range(5):
                f.write(f"user{i},{20+i}\n")
            temp_path = Path(f.name)

        try:
            # When: 청크 크기 2로 스트리밍
            chunks = list(stream_csv_chunks(temp_path, chunk_size=2))

            # Then: 3개 청크 (2 + 2 + 1)
            assert len(chunks) == 3
            assert len(chunks[0]) == 2
            assert len(chunks[1]) == 2
            assert len(chunks[2]) == 1
        finally:
            temp_path.unlink()

    def test_stream_large_csv_memory_efficient(self):
        """대용량 CSV 메모리 효율적 처리"""
        # Given: 10,000행 CSV
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.csv') as f:
            f.write("id,value\n")
            for i in range(10_000):
                f.write(f"{i},{i*2}\n")
            temp_path = Path(f.name)

        try:
            # When: 청크 크기 1000으로 스트리밍
            total_rows = 0
            for chunk in stream_csv_chunks(temp_path, chunk_size=1000):
                total_rows += len(chunk)
                # 메모리에는 1000행만 로드됨
                assert len(chunk) <= 1000

            # Then: 전체 10,000행 처리
            assert total_rows == 10_000
        finally:
            temp_path.unlink()

    def test_stream_with_encoding_detection(self):
        """인코딩 자동 감지 + 스트리밍"""
        # Given: EUC-KR 인코딩 CSV
        with tempfile.NamedTemporaryFile(mode='w', encoding='euc-kr', delete=False, suffix='.csv') as f:
            f.write("이름,나이\n")
            f.write("홍길동,30\n")
            f.write("김철수,25\n")
            temp_path = Path(f.name)

        try:
            # When: 자동 인코딩 감지 + 스트리밍
            chunks = list(stream_csv_chunks(temp_path))

            # Then: 한글 깨짐 없이 읽기
            df = chunks[0]
            assert df['이름'].iloc[0] == '홍길동'
            assert df['나이'].iloc[0] == 30
        finally:
            temp_path.unlink()
