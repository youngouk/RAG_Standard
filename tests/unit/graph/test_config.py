"""
GraphRAG YAML 설정 테스트
"""
from pathlib import Path

import pytest
import yaml


class TestGraphRAGConfig:
    """GraphRAG 설정 파일 테스트"""

    @pytest.fixture
    def config_path(self):
        """설정 파일 경로"""
        return Path("app/config/features/graph_rag.yaml")

    def test_config_file_exists(self, config_path):
        """설정 파일 존재 확인"""
        assert config_path.exists(), f"{config_path} 파일이 없습니다"

    def test_config_is_valid_yaml(self, config_path):
        """유효한 YAML인지 확인"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_config_has_graph_rag_section(self, config_path):
        """graph_rag 섹션 존재 확인"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert "graph_rag" in config

    def test_config_has_enabled_field(self, config_path):
        """enabled 필드 존재 확인"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert "enabled" in config["graph_rag"]
        # 기본값은 False (안전한 기본값)
        assert config["graph_rag"]["enabled"] is False

    def test_config_has_provider_field(self, config_path):
        """provider 필드 존재 확인"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert "provider" in config["graph_rag"]


class TestBaseConfigImport:
    """base.yaml에 graph_rag.yaml import 테스트"""

    @pytest.fixture
    def base_config_path(self):
        """base.yaml 경로"""
        return Path("app/config/base.yaml")

    def test_base_config_imports_graph_rag(self, base_config_path):
        """base.yaml이 graph_rag.yaml을 import하는지 확인"""
        with open(base_config_path) as f:
            content = f.read()

        # imports 섹션에 graph_rag.yaml이 있는지 확인
        assert "features/graph_rag.yaml" in content
