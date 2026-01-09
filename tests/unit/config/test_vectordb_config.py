"""
VectorDBConfig 스키마 테스트

Multi Vector DB 지원을 위한 설정 스키마 검증 테스트입니다.
지원 DB: weaviate, pinecone, chroma, qdrant, pgvector, mongodb
"""

import pytest
from pydantic import ValidationError


class TestVectorDBConfig:
    """VectorDBConfig Pydantic 스키마 테스트"""

    def test_valid_provider_weaviate(self):
        """weaviate provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="weaviate")
        assert config.provider == "weaviate"

    def test_valid_provider_pinecone(self):
        """pinecone provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="pinecone")
        assert config.provider == "pinecone"

    def test_valid_provider_chroma(self):
        """chroma provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="chroma")
        assert config.provider == "chroma"

    def test_valid_provider_qdrant(self):
        """qdrant provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="qdrant")
        assert config.provider == "qdrant"

    def test_valid_provider_pgvector(self):
        """pgvector provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="pgvector")
        assert config.provider == "pgvector"

    def test_valid_provider_mongodb(self):
        """mongodb provider가 유효한지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(provider="mongodb")
        assert config.provider == "mongodb"

    def test_invalid_provider_rejected(self):
        """유효하지 않은 provider가 거부되는지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        with pytest.raises(ValidationError) as exc_info:
            VectorDBConfig(provider="invalid_db")

        # 에러 메시지에 provider 관련 내용이 포함되어야 함
        error_str = str(exc_info.value)
        assert "provider" in error_str

    def test_default_provider_weaviate(self):
        """기본 provider가 weaviate인지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig()
        assert config.provider == "weaviate"

    def test_extra_fields_allowed(self):
        """DB별 추가 설정이 허용되는지 확인 (extra='allow')"""
        from app.config.schemas.retrieval import VectorDBConfig

        # Pinecone 전용 설정 예시
        config = VectorDBConfig(
            provider="pinecone",
            api_key="test-api-key",
            environment="us-east-1",
            index_name="my-index",
        )

        assert config.provider == "pinecone"
        # extra 필드 접근 확인 (model_extra 또는 직접 속성)
        assert config.api_key == "test-api-key"  # type: ignore[attr-defined]
        assert config.environment == "us-east-1"  # type: ignore[attr-defined]

    def test_model_dump_includes_extra_fields(self):
        """model_dump()가 추가 필드를 포함하는지 확인"""
        from app.config.schemas.retrieval import VectorDBConfig

        config = VectorDBConfig(
            provider="qdrant",
            url="http://localhost:6333",
            collection_name="test_collection",
        )

        dumped = config.model_dump()
        assert dumped["provider"] == "qdrant"
        assert dumped["url"] == "http://localhost:6333"
        assert dumped["collection_name"] == "test_collection"


class TestVectorDBConfigYaml:
    """base.yaml의 vector_db 섹션 테스트"""

    @pytest.fixture
    def base_yaml_config(self):
        """base.yaml 파일 로드"""
        import yaml

        with open("app/config/base.yaml") as f:
            return yaml.safe_load(f)

    def test_vector_db_section_exists(self, base_yaml_config):
        """vector_db 섹션이 base.yaml에 존재하는지 확인"""
        assert "vector_db" in base_yaml_config

    def test_vector_db_provider_exists(self, base_yaml_config):
        """vector_db.provider 설정이 존재하는지 확인"""
        assert "provider" in base_yaml_config["vector_db"]

    def test_vector_db_default_provider(self, base_yaml_config):
        """기본 provider가 환경변수 폴백으로 weaviate인지 확인"""
        provider = base_yaml_config["vector_db"]["provider"]
        # ${VECTOR_DB_PROVIDER:-weaviate} 형식 확인
        assert "weaviate" in provider or provider == "weaviate"
