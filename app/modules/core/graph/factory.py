"""
GraphRAGFactory - 설정 기반 그래프 저장소 자동 선택 팩토리

YAML 설정에 따라 적절한 그래프 저장소 인스턴스를 생성합니다.
기존 RerankerFactory, CacheFactory 패턴과 동일한 구조.

사용 예시:
    from app.modules.core.graph import GraphRAGFactory

    # YAML 설정 기반 그래프 저장소 생성
    store = GraphRAGFactory.create(config)

    # 지원 저장소 조회
    GraphRAGFactory.get_supported_stores()

지원 저장소:
    - networkx: NetworkX 기반 인메모리 그래프 (경량, 기본값)
    - neo4j: Neo4j 그래프 데이터베이스 (프로덕션)
"""
from typing import Any

from app.lib.logger import get_logger

from .interfaces import IGraphStore
from .stores import NetworkXGraphStore

logger = get_logger(__name__)


# 지원 그래프 저장소 레지스트리
SUPPORTED_GRAPH_STORES: dict[str, dict[str, Any]] = {
    # 인메모리 그래프 (경량, 기본값)
    "networkx": {
        "type": "in-memory",
        "class": "NetworkXGraphStore",
        "description": "NetworkX 기반 인메모리 그래프 (단일 인스턴스, 기본값)",
        "default_config": {},
    },
    # 그래프 데이터베이스 (프로덕션)
    "neo4j": {
        "type": "database",
        "class": "Neo4jGraphStore",
        "description": "Neo4j 그래프 데이터베이스 (프로덕션, 대규모)",
        "requires_env": "NEO4J_URI",
        "default_config": {
            "database": "neo4j",
        },
    },
}


class GraphRAGFactory:
    """
    설정 기반 그래프 저장소 팩토리

    YAML 설정 파일의 graph_rag 섹션을 읽어 적절한 저장소를 생성합니다.

    설정 예시 (features/graph_rag.yaml):
        graph_rag:
          enabled: false  # 기본 비활성화
          provider: "networkx"  # networkx, neo4j
          networkx: {}
          neo4j:
            uri: "${NEO4J_URI}"
            database: "neo4j"
    """

    @staticmethod
    def create(config: dict[str, Any]) -> IGraphStore | None:
        """
        설정 기반 그래프 저장소 인스턴스 생성

        Args:
            config: 전체 설정 딕셔너리 (graph_rag 섹션 포함)

        Returns:
            IGraphStore 인터페이스를 구현한 저장소 인스턴스
            비활성화 시 None

        Raises:
            ValueError: 지원하지 않는 프로바이더인 경우
            NotImplementedError: 미구현 프로바이더인 경우
        """
        graph_config = config.get("graph_rag", {})

        # 비활성화 체크 (기본값: False)
        if not graph_config.get("enabled", False):
            logger.info("ℹ️  GraphRAG disabled via config")
            return None

        provider = graph_config.get("provider", "networkx")

        logger.info(f"🔄 GraphRAGFactory: provider={provider}")

        if provider not in SUPPORTED_GRAPH_STORES:
            supported = list(SUPPORTED_GRAPH_STORES.keys())
            raise ValueError(
                f"지원하지 않는 그래프 저장소 프로바이더: {provider}. "
                f"지원 목록: {supported}"
            )

        if provider == "networkx":
            return GraphRAGFactory._create_networkx_store(config, graph_config)
        elif provider == "neo4j":
            return GraphRAGFactory._create_neo4j_store(config, graph_config)
        else:
            raise ValueError(f"지원하지 않는 그래프 저장소 프로바이더: {provider}")

    @staticmethod
    def _create_networkx_store(
        config: dict[str, Any],
        graph_config: dict[str, Any],
    ) -> NetworkXGraphStore:
        """NetworkX 그래프 저장소 생성"""
        store = NetworkXGraphStore()
        logger.info("✅ NetworkXGraphStore 생성")
        return store

    @staticmethod
    def _create_neo4j_store(
        config: dict[str, Any],
        graph_config: dict[str, Any],
    ) -> IGraphStore:
        """
        Neo4j 그래프 저장소 생성

        환경 변수에서 연결 정보를 읽고, YAML 설정에서 연결 풀/재시도 설정을 읽어
        Neo4jGraphStore를 생성합니다.

        Args:
            config: 전체 설정
            graph_config: graph_rag 섹션 설정

        Returns:
            Neo4jGraphStore 인스턴스

        Raises:
            ValueError: NEO4J_URI 환경 변수가 없는 경우
        """
        import os

        from .stores.neo4j_store import Neo4jGraphStore

        # YAML 설정에서 neo4j 섹션 읽기
        neo4j_section = graph_config.get("neo4j", {})
        pool_config = neo4j_section.get("connection_pool", {})
        retry_config = neo4j_section.get("retry", {})

        # 환경 변수 + YAML 설정 병합
        store_config = {
            # 환경 변수에서 읽는 연결 정보
            "uri": os.getenv("NEO4J_URI"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", ""),
            # YAML 설정에서 읽는 데이터베이스
            "database": neo4j_section.get("database", "neo4j"),
            # 연결 풀 설정 (기본값 포함)
            "max_pool_size": pool_config.get("max_pool_size", 50),
            "connection_timeout": pool_config.get("connection_timeout", 30.0),
            "query_timeout": pool_config.get("query_timeout", 60.0),
            # 재시도 설정 (기본값 포함)
            "max_retries": retry_config.get("max_attempts", 3),
            "retry_delay": retry_config.get("delay", 1.0),
        }

        # URI는 필수
        if not store_config["uri"]:
            raise ValueError(
                "Neo4j GraphStore 사용을 위해 NEO4J_URI 환경 변수가 필요합니다."
            )

        logger.info(
            f"✅ Neo4jGraphStore 생성: database={store_config['database']}, "
            f"pool_size={store_config['max_pool_size']}, "
            f"max_retries={store_config['max_retries']}"
        )

        return Neo4jGraphStore(store_config)

    @staticmethod
    def get_supported_stores() -> list[str]:
        """지원하는 모든 저장소 이름 반환"""
        return list(SUPPORTED_GRAPH_STORES.keys())

    @staticmethod
    def get_store_info(name: str) -> dict[str, Any] | None:
        """
        특정 저장소의 상세 정보 반환

        Args:
            name: 저장소 이름

        Returns:
            저장소 정보 딕셔너리 또는 None
        """
        return SUPPORTED_GRAPH_STORES.get(name)
