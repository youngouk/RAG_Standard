"""
MongoDB Atlas Retriever - 하이브리드 검색 (Dense + Sparse BM25)

주요 기능:
- $rankFusion aggregation pipeline을 사용한 하이브리드 검색
- Vector Search (Dense, 3072 dimensions, cosine)
- Full-Text Search (Sparse, BM25)
- IRetriever 인터페이스 구현

데이터 구조:
- embedding: 3072차원 float 배열 (Gemini embedding-001)
- content: 텍스트 내용
- metadata.metadata: 중첩된 메타데이터 (source_file, file_type 등)
- llm_enrichment.keywords: LLM 추출 키워드 배열

의존성:
- pymongo: MongoDB 공식 Python 드라이버 (pymongo[srv] 필수)
- app.lib.mongodb_client: MongoDB 연결 클라이언트
- app.modules.core.retrieval.interfaces: IRetriever 인터페이스
"""

import asyncio
from typing import Any, cast

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from .....lib.logger import get_logger
from .....lib.mongodb_client import MongoDBClient
from ..interfaces import SearchResult

logger = get_logger(__name__)


class MongoDBRetriever:
    """
    MongoDB Atlas 하이브리드 검색 구현

    특징:
    - MongoDB Atlas Vector Search + Full-Text Search
    - $rankFusion을 통한 RRF (Reciprocal Rank Fusion)
    - Gemini 3072d embedding 지원
    - BM25 Full-Text Search (content + llm_enrichment.keywords)

    아키텍처:
    - vectorPipeline: $vectorSearch (Dense, cosine similarity)
    - fullTextPipeline: $search (Sparse, BM25)
    - $rankFusion: RRF 기반 결과 통합

    데이터 스키마:
    - embedding: float[] (3072 dimensions)
    - content: string
    - metadata.metadata: object (중첩 구조)
    - llm_enrichment.keywords: string[] (검색 최적화용)
    """

    def __init__(
        self,
        embedder: Any,
        mongodb_client: MongoDBClient,
        collection_name: str = "documents",
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ):
        """
        MongoDB Retriever 초기화 (DI Container)

        Args:
            embedder: Dense embedding 모델 (Google Gemini)
            mongodb_client: MongoDB 클라이언트 (DI)
            collection_name: MongoDB 컬렉션 이름 (기본: "documents")
            dense_weight: Dense vector 가중치 (기본: 0.6)
            sparse_weight: float BM25 가중치 (기본: 0.4)

        Note:
            가중치 합은 1.0이 아니어도 됨 (MongoDB가 자동 정규화)
        """
        self.embedder = embedder
        self.collection_name = collection_name
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        # MongoDB 클라이언트 및 컬렉션 (DI)
        self.mongodb_client = mongodb_client
        self.collection: Collection | None = None

        # 인덱스 이름 (실제 Atlas 인덱스 이름)
        self.vector_index_name = "vector_index"
        self.fulltext_index_name = "default"

        # 통계
        self.stats = {
            "total_searches": 0,
            "hybrid_searches": 0,
            "vector_searches": 0,
            "fulltext_searches": 0,
        }

        logger.info(
            f"MongoDBRetriever 초기화: collection={collection_name}, "
            f"weights=(dense={dense_weight}, sparse={sparse_weight})"
        )

    async def initialize(self) -> None:
        """
        MongoDB Retriever 초기화 (컬렉션 접근 확인)

        작업:
        1. MongoDB 클라이언트 연결 확인
        2. 컬렉션 존재 및 접근 확인
        3. 문서 수 카운트 (초기화 검증)

        Raises:
            RuntimeError: 컬렉션 접근 실패 시
            PyMongoError: MongoDB 연결 오류 시
        """
        try:
            logger.debug("MongoDBRetriever 초기화 시작...")

            # 1. MongoDB 연결 상태 확인
            if not self.mongodb_client.ping():
                raise RuntimeError("MongoDB 연결이 활성화되지 않았습니다.")

            # 2. Collection 가져오기
            self.collection = self.mongodb_client.get_collection(self.collection_name)

            if self.collection is None:
                raise RuntimeError(f"MongoDB 컬렉션을 가져올 수 없습니다: {self.collection_name}")

            # 3. 컬렉션 접근 확인 (document count)
            doc_count = await asyncio.to_thread(self.collection.count_documents, {})

            logger.info(
                f"MongoDBRetriever 초기화 완료: collection={self.collection_name}, "
                f"documents={doc_count}"
            )

        except PyMongoError as e:
            logger.error(
                f"MongoDB 연결 오류: {str(e)}",
                extra={"collection": self.collection_name, "error_type": type(e).__name__},
            )
            raise

        except Exception as e:
            logger.error(
                f"MongoDBRetriever 초기화 실패: {str(e)}",
                extra={"collection": self.collection_name},
            )
            raise

    async def health_check(self) -> bool:
        """
        MongoDB 연결 및 컬렉션 상태 확인

        검증 항목:
        1. MongoDB ping 응답
        2. 컬렉션 접근 가능 여부

        Returns:
            정상 동작 여부 (True/False)
        """
        try:
            # 1. 컬렉션 초기화 확인
            if self.collection is None:
                logger.warning("MongoDB health check 실패: 컬렉션 미초기화")
                return False

            # 2. MongoDB ping 확인
            is_connected = self.mongodb_client.ping()

            if not is_connected:
                logger.warning("MongoDB health check 실패: 연결 끊김")
                return False

            # 3. 컬렉션 접근 확인 (count_documents with limit=1)
            await asyncio.to_thread(self.collection.count_documents, {}, limit=1)

            logger.debug("MongoDB health check 성공")
            return True

        except PyMongoError as e:
            logger.error(
                f"MongoDB health check 실패: {str(e)}", extra={"error_type": type(e).__name__}
            )
            return False

        except Exception as e:
            logger.error(f"MongoDB health check 예상치 못한 오류: {str(e)}")
            return False

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        하이브리드 검색 수행 (Dense + Sparse with Client-side RRF)

        클라이언트 사이드 RRF 방식:
        1. Vector Search와 Full-Text Search를 독립적으로 실행
        2. Python에서 RRF(Reciprocal Rank Fusion) 알고리즘으로 결과 통합
        3. Atlas tier 제약 없이 하이브리드 검색 가능

        Args:
            query: 검색 쿼리 문자열
            top_k: 반환할 최대 결과 수
            filters: 메타데이터 필터링 조건

        Returns:
            검색 결과 리스트 (SearchResult)

        Raises:
            PyMongoError: MongoDB 검색 오류 시
        """
        try:
            if self.collection is None:
                raise RuntimeError("MongoDB 컬렉션이 초기화되지 않았습니다.")

            # 1. Dense embedding 생성
            logger.debug(f"Query embedding 생성 중: query='{query[:50]}...'")
            query_embedding = await asyncio.to_thread(self.embedder.embed_query, query)

            if not isinstance(query_embedding, list):
                raise ValueError(
                    f"Embedding은 list 타입이어야 합니다. 받은 타입: {type(query_embedding)}"
                )

            # 2. Vector Search와 Full-Text Search 병렬 실행
            logger.debug(f"MongoDB 하이브리드 검색 실행 (Client-side RRF): top_k={top_k}")

            # 더 많은 결과를 가져와서 RRF로 합치기
            candidate_k = top_k * 2

            # 병렬 실행을 위한 태스크 생성
            vector_task = self._vector_search_only(
                query_embedding=query_embedding,
                top_k=candidate_k,
                filters=filters,
            )
            fulltext_task = self._fulltext_search_only(
                query=query,
                top_k=candidate_k,
                filters=filters,
            )

            # 동시 실행
            results_tuple: tuple[
                list[dict[str, Any]] | BaseException, list[dict[str, Any]] | BaseException
            ]
            results_tuple = await asyncio.gather(vector_task, fulltext_task, return_exceptions=True)
            vector_raw, fulltext_raw = results_tuple

            # 예외 처리 및 타입 안전성 확보
            vector_results: list[Any]
            if isinstance(vector_raw, Exception):
                logger.warning(f"Vector search 실패: {vector_raw}")
                vector_results = []
            else:
                vector_results = cast(list[dict[str, Any]], vector_raw)

            fulltext_results: list[Any]
            if isinstance(fulltext_raw, Exception):
                logger.warning(f"Full-text search 실패: {fulltext_raw}")
                fulltext_results = []
            else:
                fulltext_results = cast(list[dict[str, Any]], fulltext_raw)

            # 3. Client-side RRF로 결과 통합
            results = self._client_side_rank_fusion(
                vector_results=vector_results,
                fulltext_results=fulltext_results,
                top_k=top_k,
            )

            # 4. 통계 업데이트
            self.stats["total_searches"] += 1
            self.stats["hybrid_searches"] += 1

            logger.info(
                f"MongoDB 하이브리드 검색 완료 (Client-side RRF): {len(results)}개 결과 반환"
            )
            return results

        except PyMongoError as e:
            logger.error(
                f"MongoDB 검색 오류: {str(e)}",
                extra={"query": query[:100], "error_type": type(e).__name__},
            )
            # Fallback: Dense 검색만 시도
            return await self._vector_search_fallback(query, top_k, filters)

        except Exception as e:
            logger.error(f"MongoDB 검색 예상치 못한 오류: {str(e)}", extra={"query": query[:100]})
            raise

    async def _vector_search_only(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Vector Search 단독 실행

        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 결과 수
            filters: 메타데이터 필터링

        Returns:
            검색 결과 리스트 (dict with _id, content, metadata, score)
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.vector_index_name,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": top_k * 10,
                    "limit": top_k,
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        # 필터링 추가
        if filters:
            match_stage: dict[str, Any] = {"$match": {}}
            for key, value in filters.items():
                match_stage["$match"][f"metadata.metadata.{key}"] = value
            pipeline.insert(1, match_stage)

        if self.collection is None:
            logger.error("Collection이 초기화되지 않음")
            return []

        cursor = await asyncio.to_thread(self.collection.aggregate, pipeline)
        results = await asyncio.to_thread(list, cursor)
        return results

    async def _fulltext_search_only(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Full-Text Search 단독 실행

        Args:
            query: 검색 쿼리 문자열
            top_k: 반환할 결과 수
            filters: 메타데이터 필터링

        Returns:
            검색 결과 리스트 (dict with _id, content, metadata, score)
        """
        pipeline = [
            {
                "$search": {
                    "index": self.fulltext_index_name,
                    "text": {
                        "query": query,
                        "path": "content",
                    },
                }
            },
            {"$limit": top_k},
            {
                "$project": {
                    "_id": 1,
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "searchScore"},
                }
            },
        ]

        # 필터링 추가
        if filters:
            match_stage: dict[str, Any] = {"$match": {}}
            for key, value in filters.items():
                match_stage["$match"][f"metadata.metadata.{key}"] = value
            pipeline.insert(1, match_stage)

        if self.collection is None:
            logger.error("Collection이 초기화되지 않음")
            return []

        cursor = await asyncio.to_thread(
            lambda: self.collection.aggregate(pipeline)  # type: ignore[union-attr,arg-type]
        )
        results = await asyncio.to_thread(list, cursor)
        return results

    def _client_side_rank_fusion(
        self,
        vector_results: list[dict[str, Any]],
        fulltext_results: list[dict[str, Any]],
        top_k: int,
        k: int = 60,
    ) -> list[SearchResult]:
        """
        Client-side RRF (Reciprocal Rank Fusion) 구현

        RRF 알고리즘:
        - score(doc) = Σ(weight_i / (k + rank_i))
        - k=60 (논문 기준 기본값)
        - 여러 검색에서 높은 순위를 받은 문서가 최종 상위에 위치

        Args:
            vector_results: Vector Search 결과
            fulltext_results: Full-Text Search 결과
            top_k: 최종 반환할 결과 수
            k: RRF 상수 (기본 60)

        Returns:
            통합된 검색 결과 리스트 (SearchResult)
        """
        # 문서별 RRF 점수 계산
        doc_scores: dict[str, float] = {}
        doc_data: dict[str, dict[str, Any]] = {}

        # Vector Search 결과 처리
        for rank, doc in enumerate(vector_results, start=1):
            doc_id = str(doc["_id"])
            rrf_score = self.dense_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score
            doc_data[doc_id] = doc

        # Full-Text Search 결과 처리
        for rank, doc in enumerate(fulltext_results, start=1):
            doc_id = str(doc["_id"])
            rrf_score = self.sparse_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score

            # Full-text에만 있는 문서는 doc_data에 추가
            if doc_id not in doc_data:
                doc_data[doc_id] = doc

        # 점수로 정렬
        sorted_doc_ids = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # SearchResult로 변환
        results = []
        for doc_id, score in sorted_doc_ids:
            doc = doc_data[doc_id]
            results.append(
                SearchResult(
                    id=doc_id,
                    content=doc.get("content", ""),
                    score=score,
                    metadata=doc.get("metadata", {}),
                )
            )

        return results

    async def _vector_search_fallback(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Vector search fallback (하이브리드 검색 실패 시)

        $vectorSearch만 사용하여 Dense 검색 수행

        Args:
            query: 검색 쿼리 문자열
            top_k: 반환할 최대 결과 수
            filters: 메타데이터 필터링 조건

        Returns:
            검색 결과 리스트 (SearchResult)
        """
        try:
            logger.warning("Fallback: Vector search만 수행")

            # Query embedding 생성
            query_embedding = await asyncio.to_thread(self.embedder.embed_query, query)

            # Vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.vector_index_name,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": top_k * 10,
                        "limit": top_k,
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "content": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]

            # 필터링 추가 (중첩된 메타데이터 구조)
            if filters:
                match_stage: dict[str, Any] = {"$match": {}}
                for key, value in filters.items():
                    match_stage["$match"][f"metadata.metadata.{key}"] = value
                pipeline.insert(1, match_stage)

            if self.collection is None:
                logger.error("Collection이 초기화되지 않음")
                return []

            # MongoDB aggregate 실행
            cursor = await asyncio.to_thread(self.collection.aggregate, pipeline)

            # 결과 변환
            results = []
            docs = await asyncio.to_thread(list, cursor)

            for doc in docs:
                results.append(
                    SearchResult(
                        id=str(doc["_id"]),
                        content=doc.get("content", ""),
                        score=doc.get("score", 0.0),
                        metadata=doc.get("metadata", {}),
                    )
                )

            self.stats["vector_searches"] += 1
            logger.info(f"Fallback vector search 완료: {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"Fallback vector search 실패: {str(e)}")
            return []
