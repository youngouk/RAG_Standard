"""
평가 시스템 설정 테스트
YAML 설정 로딩 및 검증
"""

from pathlib import Path

import yaml


class TestEvaluationConfigFile:
    """evaluation.yaml 설정 파일 테스트"""

    def test_evaluation_yaml_exists(self):
        """evaluation.yaml 파일 존재 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        assert config_path.exists(), "evaluation.yaml 파일이 없습니다"

    def test_evaluation_yaml_is_valid(self):
        """evaluation.yaml이 유효한 YAML인지 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert config is not None
        assert "evaluation" in config

    def test_evaluation_config_has_required_fields(self):
        """evaluation 설정에 필수 필드가 있는지 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        eval_config = config["evaluation"]
        required_fields = ["enabled", "provider"]

        for field in required_fields:
            assert field in eval_config, f"필수 필드 누락: {field}"

    def test_evaluation_provider_internal_config(self):
        """internal 프로바이더 설정 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        eval_config = config["evaluation"]
        assert "internal" in eval_config

        internal_config = eval_config["internal"]
        assert "model" in internal_config
        assert "timeout" in internal_config

    def test_evaluation_ragas_config(self):
        """ragas 프로바이더 설정 확인 (Phase 2용)"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        eval_config = config["evaluation"]
        assert "ragas" in eval_config

        ragas_config = eval_config["ragas"]
        assert "metrics" in ragas_config
        assert "batch_size" in ragas_config

    def test_evaluation_feedback_config(self):
        """피드백 설정 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        eval_config = config["evaluation"]
        assert "feedback" in eval_config

        feedback_config = eval_config["feedback"]
        assert "enabled" in feedback_config
        assert "storage" in feedback_config

    def test_evaluation_thresholds_config(self):
        """품질 임계값 설정 확인"""
        config_path = Path("app/config/features/evaluation.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        eval_config = config["evaluation"]
        assert "thresholds" in eval_config

        thresholds = eval_config["thresholds"]
        assert "min_acceptable" in thresholds
        assert "good_quality" in thresholds
        assert "excellent_quality" in thresholds


class TestBaseConfigImportsEvaluation:
    """base.yaml에서 evaluation.yaml import 확인"""

    def test_base_config_imports_evaluation(self):
        """base.yaml의 imports에 evaluation.yaml이 포함되어 있는지 확인"""
        config_path = Path("app/config/base.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        imports = config.get("imports", [])
        evaluation_imported = any("evaluation" in imp for imp in imports)

        assert evaluation_imported, "base.yaml의 imports에 evaluation.yaml이 없습니다"
