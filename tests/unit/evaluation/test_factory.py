"""
EvaluatorFactory 단위 테스트

설정 기반 평가기 생성 검증.
GraphRAGFactory 패턴을 따라 구현된 팩토리 테스트.

테스트 범위:
- SUPPORTED_EVALUATORS 레지스트리 검증
- EvaluatorFactory 정적 메서드 검증
- 설정 기반 평가기 생성 검증
- 에러 처리 검증
"""
from unittest.mock import MagicMock

import pytest


class TestSupportedEvaluatorsRegistry:
    """SUPPORTED_EVALUATORS 레지스트리 테스트"""

    def test_registry_exists(self):
        """지원 평가기 레지스트리 존재 확인"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        assert isinstance(SUPPORTED_EVALUATORS, dict)
        assert len(SUPPORTED_EVALUATORS) > 0

    def test_registry_contains_internal(self):
        """레지스트리에 internal이 포함되어 있는지 확인"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        assert "internal" in SUPPORTED_EVALUATORS

    def test_registry_contains_ragas(self):
        """레지스트리에 ragas가 포함되어 있는지 확인 (Phase 2 예정)"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        assert "ragas" in SUPPORTED_EVALUATORS

    def test_each_evaluator_has_required_fields(self):
        """각 평가기 정보에 필수 필드가 있는지 확인"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        required_fields = {"type", "class", "description", "default_config"}

        for name, info in SUPPORTED_EVALUATORS.items():
            for field in required_fields:
                assert field in info, f"{name}에 {field} 필드 없음"

    def test_internal_evaluator_info(self):
        """internal 평가기 정보 상세 검증"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        internal_info = SUPPORTED_EVALUATORS["internal"]

        assert internal_info["type"] == "realtime"
        assert internal_info["class"] == "InternalEvaluator"
        assert "model" in internal_info["default_config"]
        assert "timeout" in internal_info["default_config"]

    def test_ragas_evaluator_info(self):
        """ragas 평가기 정보 상세 검증"""
        from app.modules.core.evaluation.factory import SUPPORTED_EVALUATORS

        ragas_info = SUPPORTED_EVALUATORS["ragas"]

        assert ragas_info["type"] == "batch"
        assert ragas_info["class"] == "RagasEvaluator"
        assert "requires_package" in ragas_info


class TestEvaluatorFactoryStaticMethods:
    """EvaluatorFactory 정적 메서드 테스트"""

    def test_get_supported_evaluators(self):
        """지원 평가기 목록 조회"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        evaluators = EvaluatorFactory.get_supported_evaluators()

        assert isinstance(evaluators, list)
        assert "internal" in evaluators
        assert "ragas" in evaluators

    def test_get_evaluator_info_existing(self):
        """존재하는 평가기 정보 조회"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        info = EvaluatorFactory.get_evaluator_info("internal")

        assert info is not None
        assert info["class"] == "InternalEvaluator"

    def test_get_evaluator_info_non_existing(self):
        """존재하지 않는 평가기 정보 조회 시 None 반환"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        info = EvaluatorFactory.get_evaluator_info("non-existing")

        assert info is None

    def test_list_evaluators_by_type_realtime(self):
        """타입별 평가기 목록 조회 - realtime"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        realtime_evaluators = EvaluatorFactory.list_evaluators_by_type("realtime")

        assert isinstance(realtime_evaluators, list)
        assert "internal" in realtime_evaluators

    def test_list_evaluators_by_type_batch(self):
        """타입별 평가기 목록 조회 - batch"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        batch_evaluators = EvaluatorFactory.list_evaluators_by_type("batch")

        assert isinstance(batch_evaluators, list)
        assert "ragas" in batch_evaluators


class TestEvaluatorFactoryCreate:
    """EvaluatorFactory.create() 메서드 테스트"""

    def test_create_internal_evaluator(self):
        """Internal 평가기 생성"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
            }
        }
        mock_llm_client = MagicMock()

        evaluator = EvaluatorFactory.create(config, llm_client=mock_llm_client)

        assert evaluator is not None
        assert evaluator.name == "internal"

    def test_create_internal_evaluator_with_custom_config(self):
        """커스텀 설정으로 Internal 평가기 생성"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
                "internal": {
                    "model": "custom-model",
                    "timeout": 30.0,
                },
            }
        }
        mock_llm_client = MagicMock()

        evaluator = EvaluatorFactory.create(config, llm_client=mock_llm_client)

        assert evaluator is not None
        assert evaluator.name == "internal"
        # 내부 설정 확인 (private 속성이므로 _model 접근)
        assert evaluator._model == "custom-model"
        assert evaluator._timeout == 30.0

    def test_create_with_defaults(self):
        """기본값으로 평가기 생성 (provider 미지정 시 internal 사용)"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
            }
        }
        mock_llm_client = MagicMock()

        evaluator = EvaluatorFactory.create(config, llm_client=mock_llm_client)

        assert evaluator is not None
        assert evaluator.name == "internal"

    def test_create_disabled_returns_none(self):
        """비활성화 시 None 반환"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": False,
            }
        }

        evaluator = EvaluatorFactory.create(config)

        assert evaluator is None

    def test_create_with_empty_config_returns_none(self):
        """빈 설정으로 생성 시 None 반환 (기본 비활성화)"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {}

        evaluator = EvaluatorFactory.create(config)

        assert evaluator is None

    def test_create_with_invalid_provider_raises_error(self):
        """유효하지 않은 프로바이더로 생성 시 에러"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "invalid-provider",
            }
        }

        with pytest.raises(ValueError, match="지원하지 않는"):
            EvaluatorFactory.create(config)

    def test_create_ragas_evaluator(self):
        """Ragas 평가기 생성"""
        from app.modules.core.evaluation.factory import EvaluatorFactory
        from app.modules.core.evaluation.ragas_evaluator import RagasEvaluator

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "ragas",
                "ragas": {
                    "metrics": ["faithfulness", "answer_relevancy"],
                    "batch_size": 5,
                },
            }
        }

        evaluator = EvaluatorFactory.create(config)

        assert evaluator is not None
        assert isinstance(evaluator, RagasEvaluator)
        assert evaluator.name == "ragas"
        assert evaluator._batch_size == 5

    def test_create_internal_without_llm_client(self):
        """LLM 클라이언트 없이 Internal 평가기 생성 (평가 불가 상태)"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
            }
        }

        evaluator = EvaluatorFactory.create(config, llm_client=None)

        assert evaluator is not None
        assert evaluator.name == "internal"
        # LLM 클라이언트가 없으므로 is_available() == False
        assert evaluator.is_available() is False


class TestEvaluatorFactoryProtocolCompliance:
    """생성된 평가기가 IEvaluator Protocol을 준수하는지 테스트"""

    def test_created_evaluator_has_required_methods(self):
        """생성된 평가기가 필수 메서드를 가지는지 확인"""
        from app.modules.core.evaluation.factory import EvaluatorFactory

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
            }
        }
        mock_llm_client = MagicMock()

        evaluator = EvaluatorFactory.create(config, llm_client=mock_llm_client)

        # Protocol 필수 메서드/속성 확인
        assert hasattr(evaluator, "name")
        assert hasattr(evaluator, "evaluate")
        assert hasattr(evaluator, "batch_evaluate")
        assert hasattr(evaluator, "is_available")

    def test_created_evaluator_is_protocol_instance(self):
        """생성된 평가기가 IEvaluator Protocol 인스턴스인지 확인"""
        from app.modules.core.evaluation.factory import EvaluatorFactory
        from app.modules.core.evaluation.interfaces import IEvaluator

        config = {
            "evaluation": {
                "enabled": True,
                "provider": "internal",
            }
        }
        mock_llm_client = MagicMock()

        evaluator = EvaluatorFactory.create(config, llm_client=mock_llm_client)

        # Protocol은 runtime_checkable이므로 isinstance 검사 가능
        assert isinstance(evaluator, IEvaluator)
