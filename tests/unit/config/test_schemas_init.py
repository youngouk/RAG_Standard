"""
app/config/schemas/__init__.py 모듈 테스트

Phase 2 R2.1: 레거시 동적 import 제거, 직접 함수 정의로 전환
TDD RED 단계 - 테스트 먼저 작성
"""

from pathlib import Path


class TestDetectDuplicateKeysInYaml:
    """detect_duplicate_keys_in_yaml 함수 테스트"""

    def test_import_from_schemas_package(self) -> None:
        """schemas 패키지에서 함수 import 가능 확인"""
        from app.config.schemas import detect_duplicate_keys_in_yaml

        assert callable(detect_duplicate_keys_in_yaml)

    def test_no_duplicates(self, tmp_path: Path) -> None:
        """중복 키가 없는 YAML 파일"""
        from app.config.schemas import detect_duplicate_keys_in_yaml

        yaml_content = """
app:
  name: test
server:
  port: 8000
database:
  host: localhost
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        result = detect_duplicate_keys_in_yaml(str(yaml_file))
        assert result == []

    def test_with_duplicates(self, tmp_path: Path) -> None:
        """중복 키가 있는 YAML 파일"""
        from app.config.schemas import detect_duplicate_keys_in_yaml

        yaml_content = """app:
  name: first
server:
  port: 8000
app:
  name: second
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        result = detect_duplicate_keys_in_yaml(str(yaml_file))
        assert len(result) == 1
        assert "app" in result[0]


class TestValidateConfigDict:
    """validate_config_dict 함수 테스트"""

    def test_import_from_schemas_package(self) -> None:
        """schemas 패키지에서 함수 import 가능 확인"""
        from app.config.schemas import validate_config_dict

        assert callable(validate_config_dict)


class TestBM25ConfigAndPrivacyConfig:
    """BM25Config, PrivacyConfig 클래스 테스트"""

    def test_import_bm25_config(self) -> None:
        """BM25Config import 가능 확인"""
        from app.config.schemas import BM25Config

        assert BM25Config is not None

    def test_import_privacy_config(self) -> None:
        """PrivacyConfig import 가능 확인"""
        from app.config.schemas import PrivacyConfig

        assert PrivacyConfig is not None


class TestSchemasPackageExports:
    """schemas 패키지 __all__ export 테스트"""

    def test_all_exports_available(self) -> None:
        """모든 __all__ 항목이 import 가능"""
        from app.config import schemas

        expected_exports = [
            "BaseConfig",
            "RetrievalConfig",
            "GenerationConfig",
            "RerankingConfig",
            "RootConfig",
            "validate_config",
            "detect_duplicate_keys_in_yaml",
            "validate_config_dict",
            "BM25Config",
            "PrivacyConfig",
        ]

        for export in expected_exports:
            assert hasattr(schemas, export), f"{export}가 schemas에서 export되지 않음"
