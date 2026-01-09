"""
GraphRAGFactory 단위 테스트
설정 기반 그래프 저장소 생성 검증
"""
import pytest


class TestSupportedGraphStoresRegistry:
    """SUPPORTED_GRAPH_STORES 레지스트리 테스트"""

    def test_registry_exists(self):
        """지원 그래프 저장소 레지스트리 존재 확인"""
        from app.modules.core.graph.factory import SUPPORTED_GRAPH_STORES

        assert isinstance(SUPPORTED_GRAPH_STORES, dict)
        assert len(SUPPORTED_GRAPH_STORES) > 0

    def test_registry_contains_networkx(self):
        """레지스트리에 networkx가 포함되어 있는지 확인"""
        from app.modules.core.graph.factory import SUPPORTED_GRAPH_STORES

        assert "networkx" in SUPPORTED_GRAPH_STORES

    def test_each_store_has_required_fields(self):
        """각 저장소 정보에 필수 필드가 있는지 확인"""
        from app.modules.core.graph.factory import SUPPORTED_GRAPH_STORES

        required_fields = {"type", "class", "description", "default_config"}

        for store_name, store_info in SUPPORTED_GRAPH_STORES.items():
            for field in required_fields:
                assert field in store_info, f"{store_name}에 {field} 필드 없음"


class TestGraphRAGFactoryStaticMethods:
    """GraphRAGFactory 정적 메서드 테스트"""

    def test_get_supported_stores(self):
        """지원 저장소 목록 조회"""
        from app.modules.core.graph.factory import GraphRAGFactory

        stores = GraphRAGFactory.get_supported_stores()
        assert "networkx" in stores

    def test_get_store_info_existing(self):
        """존재하는 저장소 정보 조회"""
        from app.modules.core.graph.factory import GraphRAGFactory

        info = GraphRAGFactory.get_store_info("networkx")
        assert info is not None
        assert info["class"] == "NetworkXGraphStore"

    def test_get_store_info_non_existing(self):
        """존재하지 않는 저장소 정보 조회 시 None 반환"""
        from app.modules.core.graph.factory import GraphRAGFactory

        info = GraphRAGFactory.get_store_info("non-existing")
        assert info is None


class TestGraphRAGFactoryCreate:
    """GraphRAGFactory.create() 메서드 테스트"""

    def test_create_networkx_store(self):
        """NetworkX 저장소 생성"""
        from app.modules.core.graph.factory import GraphRAGFactory

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "networkx",
            }
        }
        store = GraphRAGFactory.create(config)
        assert store is not None
        assert store.__class__.__name__ == "NetworkXGraphStore"

    def test_create_with_defaults(self):
        """기본값으로 저장소 생성"""
        from app.modules.core.graph.factory import GraphRAGFactory

        config = {
            "graph_rag": {
                "enabled": True,
            }
        }
        store = GraphRAGFactory.create(config)
        assert store.__class__.__name__ == "NetworkXGraphStore"

    def test_create_disabled_returns_none(self):
        """비활성화 시 None 반환"""
        from app.modules.core.graph.factory import GraphRAGFactory

        config = {
            "graph_rag": {
                "enabled": False,
            }
        }
        store = GraphRAGFactory.create(config)
        assert store is None

    def test_create_with_empty_config_returns_none(self):
        """빈 설정으로 생성 시 None 반환 (기본 비활성화)"""
        from app.modules.core.graph.factory import GraphRAGFactory

        config = {}
        store = GraphRAGFactory.create(config)
        assert store is None

    def test_create_with_invalid_provider_raises_error(self):
        """유효하지 않은 프로바이더로 생성 시 에러"""
        from app.modules.core.graph.factory import GraphRAGFactory

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "invalid-provider",
            }
        }
        with pytest.raises(ValueError, match="지원하지 않는"):
            GraphRAGFactory.create(config)


class TestGraphRAGFactoryNeo4j:
    """Neo4j 저장소 테스트"""

    def test_neo4j_in_registry(self):
        """Neo4j가 레지스트리에 있는지 확인"""
        from app.modules.core.graph.factory import SUPPORTED_GRAPH_STORES

        assert "neo4j" in SUPPORTED_GRAPH_STORES

    def test_create_neo4j_without_env_raises_error(self, monkeypatch):
        """환경 변수 없이 Neo4j 저장소 생성 시 ValueError 발생"""
        from app.modules.core.graph.factory import GraphRAGFactory

        # 환경 변수 제거 (혹시 설정되어 있을 경우)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
            }
        }
        with pytest.raises(ValueError, match="NEO4J_URI"):
            GraphRAGFactory.create(config)

    def test_create_neo4j_with_env(self, monkeypatch):
        """환경 변수가 설정된 경우 Neo4j 저장소 생성 성공"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        # 환경 변수 설정
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "testpassword")

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
                "database": "testdb",
            }
        }

        # Neo4j 드라이버를 Mock으로 대체
        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            # 저장소가 생성되었는지 확인
            assert store is not None
            assert store.__class__.__name__ == "Neo4jGraphStore"
            mock_driver.assert_called_once()

    def test_create_neo4j_with_default_user(self, monkeypatch):
        """NEO4J_USER 없이도 기본값으로 생성 (비밀번호 없으면 auth=None)"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        # NEO4J_URI만 설정 (USER와 PASSWORD 없음)
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
            }
        }

        # Neo4j 드라이버를 Mock으로 대체
        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            assert store is not None
            # 드라이버 호출 확인 (URI와 auth 파라미터)
            mock_driver.assert_called_once()
            call_args = mock_driver.call_args
            # 첫 번째 위치 인자 (URI)
            assert call_args[0][0] == "bolt://localhost:7687"
            # user와 password 둘 다 truthy가 아니면 auth=None
            # (password가 빈 문자열이므로 falsy)
            assert call_args.kwargs["auth"] is None

    def test_create_neo4j_uses_database_from_config(self, monkeypatch):
        """config에서 database 설정을 사용"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password123")

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
                "neo4j": {
                    "database": "custom_database",
                },
            }
        }

        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            assert store is not None
            # database 설정이 올바르게 전달되었는지 확인
            assert store._database == "custom_database"

    def test_create_neo4j_with_pool_config(self, monkeypatch):
        """Factory가 연결 풀 설정을 전달하는지 확인"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password123")

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
                "neo4j": {
                    "database": "testdb",
                    "connection_pool": {
                        "max_pool_size": 100,
                        "connection_timeout": 60.0,
                        "query_timeout": 120.0,
                    },
                },
            }
        }

        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            # 연결 풀 설정이 전달되었는지 확인
            assert store is not None
            assert store._max_pool_size == 100
            assert store._connection_timeout == 60.0
            assert store._query_timeout == 120.0

    def test_create_neo4j_with_retry_config(self, monkeypatch):
        """Factory가 재시도 설정을 전달하는지 확인"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password123")

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
                "neo4j": {
                    "retry": {
                        "max_attempts": 5,
                        "delay": 2.0,
                    },
                },
            }
        }

        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            # 재시도 설정이 전달되었는지 확인
            assert store is not None
            assert store._max_retries == 5
            assert store._retry_delay == 2.0

    def test_create_neo4j_with_default_pool_config(self, monkeypatch):
        """연결 풀 설정이 없으면 기본값 사용"""
        from unittest.mock import MagicMock, patch

        from app.modules.core.graph.factory import GraphRAGFactory

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password123")

        config = {
            "graph_rag": {
                "enabled": True,
                "provider": "neo4j",
                "neo4j": {},  # 빈 neo4j 설정
            }
        }

        with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
            mock_driver.return_value = MagicMock()
            store = GraphRAGFactory.create(config)

            # 기본값 확인
            assert store is not None
            assert store._max_pool_size == 50  # 기본값
            assert store._connection_timeout == 30.0  # 기본값
            assert store._query_timeout == 60.0  # 기본값
            assert store._max_retries == 3  # 기본값
            assert store._retry_delay == 1.0  # 기본값
