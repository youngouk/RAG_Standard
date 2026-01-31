"""
easy_start 데이터 로드 스크립트 단위 테스트

ChromaDB에 샘플 데이터를 올바르게 적재하는지 검증합니다.
"""


import pytest


class TestPrepareDocuments:
    """문서 준비 함수 테스트"""

    def test_returns_list_with_correct_fields(self):
        """
        샘플 데이터를 ChromaDB 형식으로 변환

        Given: sample_data.json의 문서 1개
        When: prepare_documents() 호출
        Then: id, content, metadata 필드를 가진 리스트 반환
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {
                "id": "faq-001",
                "title": "RAG 시스템이란?",
                "content": "RAG는 검색 증강 생성 기술입니다.",
                "metadata": {"category": "기술 소개", "tags": ["RAG"]},
            }
        ]

        result = prepare_documents(raw_docs)

        assert len(result) == 1
        assert result[0]["id"] == "faq-001"
        assert "RAG 시스템이란?" in result[0]["content"]
        assert "RAG는 검색 증강 생성" in result[0]["content"]
        assert result[0]["metadata"]["category"] == "기술 소개"
        assert result[0]["metadata"]["source"] == "quickstart_sample"

    def test_merges_title_and_content(self):
        """
        title + content를 합쳐서 content 필드 생성

        Given: title과 content가 별도인 문서
        When: prepare_documents() 호출
        Then: "title\n\ncontent" 형식으로 병합
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {
                "id": "test-001",
                "title": "제목",
                "content": "본문 내용",
                "metadata": {"category": "테스트"},
            }
        ]

        result = prepare_documents(raw_docs)
        assert result[0]["content"] == "제목\n\n본문 내용"

    def test_empty_list(self):
        """
        빈 문서 리스트 처리

        Given: 빈 리스트
        When: prepare_documents() 호출
        Then: 빈 리스트 반환
        """
        from easy_start.load_data import prepare_documents

        result = prepare_documents([])
        assert result == []

    def test_skips_documents_without_id(self):
        """
        id가 없는 문서는 건너뜀

        Given: id 필드가 없는 문서
        When: prepare_documents() 호출
        Then: 해당 문서 스킵
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {"title": "제목", "content": "내용"},  # id 없음
            {"id": "ok-001", "title": "정상", "content": "정상 문서"},
        ]

        result = prepare_documents(raw_docs)
        assert len(result) == 1
        assert result[0]["id"] == "ok-001"

    def test_skips_documents_without_content(self):
        """
        content가 없는 문서는 건너뜀

        Given: content 필드가 없는 문서
        When: prepare_documents() 호출
        Then: 해당 문서 스킵
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {"id": "no-content", "title": "제목만"},
        ]

        result = prepare_documents(raw_docs)
        assert result == []

    def test_handles_missing_metadata(self):
        """
        metadata가 없는 문서도 정상 처리

        Given: metadata 필드가 없는 문서
        When: prepare_documents() 호출
        Then: 기본 metadata로 변환
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {"id": "no-meta", "title": "제목", "content": "내용"},
        ]

        result = prepare_documents(raw_docs)
        assert len(result) == 1
        assert result[0]["metadata"]["source"] == "quickstart_sample"
        assert result[0]["metadata"]["file_type"] == "FAQ"  # 기본값

    def test_handles_missing_title(self):
        """
        title이 없는 문서도 content만으로 처리

        Given: title 없는 문서
        When: prepare_documents() 호출
        Then: content만으로 full_content 구성
        """
        from easy_start.load_data import prepare_documents

        raw_docs = [
            {"id": "no-title", "content": "본문만 있음"},
        ]

        result = prepare_documents(raw_docs)
        assert len(result) == 1
        assert result[0]["content"] == "본문만 있음"


class TestBm25Index:
    """BM25 인덱스 관련 테스트"""

    def test_build_bm25_index(self):
        """
        BM25 인덱스 구축 후 검색 가능

        Given: 문서 리스트
        When: build_bm25_index() 호출
        Then: 검색 가능한 BM25Index 인스턴스 반환
        """
        pytest.importorskip("kiwipiepy")
        pytest.importorskip("rank_bm25")

        from easy_start.load_data import build_bm25_index

        docs = [
            {"id": "1", "content": "RAG 시스템 설치 가이드", "metadata": {}},
            {"id": "2", "content": "채팅 API 사용법", "metadata": {}},
        ]

        index = build_bm25_index(docs)

        assert hasattr(index, "search")
        results = index.search("설치", top_k=2)
        assert len(results) > 0

    def test_save_and_load_bm25_index(self, tmp_path):
        """
        BM25 인덱스 저장/로드 왕복 테스트

        Given: 구축된 BM25 인덱스
        When: save → load 수행
        Then: 로드된 인덱스로 동일한 검색 결과 반환
        """
        pytest.importorskip("kiwipiepy")
        pytest.importorskip("rank_bm25")

        from easy_start.load_data import (
            build_bm25_index,
            load_bm25_index,
            save_bm25_index,
        )

        docs = [
            {"id": "1", "content": "RAG 시스템 설치 가이드", "metadata": {}},
            {"id": "2", "content": "채팅 API 사용법", "metadata": {}},
        ]

        # 구축 → 저장
        index = build_bm25_index(docs)
        index_path = str(tmp_path / "test_bm25.pkl")
        save_bm25_index(index, index_path)

        # 로드 → 검색
        loaded = load_bm25_index(index_path)
        assert hasattr(loaded, "search")
        results = loaded.search("설치", top_k=2)
        assert len(results) > 0
