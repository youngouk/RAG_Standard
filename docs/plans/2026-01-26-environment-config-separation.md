# 환경별 설정 분리 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 환경(dev/test/prod)에 따라 다른 설정값을 적용하여 각 환경에 최적화된 동작 보장

**Architecture:** 기존 `environments/*.yaml` 파일에 feature config 설정 추가. ConfigLoader가 base + environment 설정을 병합하는 기존 패턴 활용.

**Tech Stack:** YAML, Pydantic, pytest

---

## 현재 상태 분석

| 설정 | 파일 | 현재 값 | 문제점 |
|------|------|---------|--------|
| `reranking.min_score` | `reranking.yaml:22` | `0.0` | 프로덕션에서 0.05 권장 |
| `scoring.collection_weight_enabled` | `rag.yaml:67` | `false` | 도메인별 조정 필요 |
| `scoring.file_type_weight_enabled` | `rag.yaml:81` | `false` | 도메인별 조정 필요 |

## 목표 설정값

| 환경 | reranking.min_score | scoring 가중치 | 이유 |
|------|---------------------|----------------|------|
| **development** | `0.0` | `false` | 모든 결과 확인 가능 |
| **test** | `0.0` | `false` | 일관된 테스트 결과 |
| **production** | `0.05` | `true` (선택적) | 저품질 결과 필터링 |

---

### Task 1: Production 환경 설정 추가

**Files:**
- Modify: `app/config/environments/production.yaml:82-93`
- Test: `tests/unit/config/test_environment_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/config/test_environment_config.py (새 파일)
"""환경별 설정 분리 테스트"""

import os
from unittest.mock import patch

import pytest


class TestEnvironmentConfigSeparation:
    """환경별 설정 분리 테스트"""

    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False)
    def test_production_reranking_min_score(self):
        """프로덕션 환경에서 reranking.min_score가 0.05인지 확인"""
        # 설정 모듈 리로드 필요 (캐시된 설정 제거)
        from importlib import reload
        import app.config.loader as loader_module
        reload(loader_module)

        from app.config.loader import ConfigLoader

        config = ConfigLoader.load()

        assert config.get("reranking", {}).get("min_score") == 0.05

    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    def test_development_reranking_min_score(self):
        """개발 환경에서 reranking.min_score가 0.0인지 확인"""
        from importlib import reload
        import app.config.loader as loader_module
        reload(loader_module)

        from app.config.loader import ConfigLoader

        config = ConfigLoader.load()

        assert config.get("reranking", {}).get("min_score") == 0.0

    @patch.dict(os.environ, {"ENVIRONMENT": "test"}, clear=False)
    def test_test_reranking_min_score(self):
        """테스트 환경에서 reranking.min_score가 0.0인지 확인"""
        from importlib import reload
        import app.config.loader as loader_module
        reload(loader_module)

        from app.config.loader import ConfigLoader

        config = ConfigLoader.load()

        assert config.get("reranking", {}).get("min_score") == 0.0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/config/test_environment_config.py -v
```

Expected: FAIL (production test - min_score가 0.0)

**Step 3: Update production.yaml**

`app/config/environments/production.yaml` 끝에 추가:

```yaml
# 리랭킹 (프로덕션 환경) - 환경별 분리
reranking:
  enabled: true
  min_score: 0.05  # ✅ 프로덕션: 저품질 결과 필터링
  timeout: 30
  max_retries: 3

# 스코어링 (프로덕션 환경) - 도메인별 가중치 활성화 가능
scoring:
  collection_weight_enabled: true  # ✅ 프로덕션: 컬렉션 가중치 활성화
  file_type_weight_enabled: true   # ✅ 프로덕션: 파일타입 가중치 활성화
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/config/test_environment_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add app/config/environments/production.yaml tests/unit/config/test_environment_config.py
git commit -m "기능: 프로덕션 환경 설정 분리 - reranking.min_score, scoring 가중치"
```

---

### Task 2: Development 환경 설정 추가

**Files:**
- Modify: `app/config/environments/development.yaml:53`

**Step 1: 테스트 이미 작성됨 (Task 1)**

**Step 2: Update development.yaml**

`app/config/environments/development.yaml` 끝에 추가:

```yaml
# 리랭킹 (개발 환경)
reranking:
  min_score: 0.0  # 개발: 모든 결과 포함 (디버깅용)

# 스코어링 (개발 환경)
scoring:
  collection_weight_enabled: false  # 개발: 순수 RRF 점수
  file_type_weight_enabled: false
```

**Step 3: Run test**

```bash
uv run pytest tests/unit/config/test_environment_config.py::TestEnvironmentConfigSeparation::test_development_reranking_min_score -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add app/config/environments/development.yaml
git commit -m "기능: 개발 환경 설정 분리 - reranking, scoring"
```

---

### Task 3: Test 환경 설정 추가

**Files:**
- Modify: `app/config/environments/test.yaml:64`

**Step 1: Update test.yaml**

`app/config/environments/test.yaml` 끝에 추가:

```yaml
# 리랭킹 (테스트 환경)
reranking:
  min_score: 0.0  # 테스트: 일관된 결과

# 스코어링 (테스트 환경)
scoring:
  collection_weight_enabled: false  # 테스트: 순수 RRF 점수
  file_type_weight_enabled: false
```

**Step 2: Run test**

```bash
uv run pytest tests/unit/config/test_environment_config.py::TestEnvironmentConfigSeparation::test_test_reranking_min_score -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add app/config/environments/test.yaml
git commit -m "기능: 테스트 환경 설정 분리 - reranking, scoring"
```

---

### Task 4: Feature Config 주석 업데이트

**Files:**
- Modify: `app/config/features/reranking.yaml:22`
- Modify: `app/config/features/rag.yaml:67,81`

**Step 1: Update reranking.yaml 주석**

```yaml
# 기존
min_score: 0.0  # 🔧 테스트용: 모든 결과 포함 (프로덕션에서는 0.05 권장)

# 변경
min_score: 0.0  # 기본값 (환경별 설정: environments/*.yaml에서 오버라이드)
```

**Step 2: Update rag.yaml 주석**

```yaml
# 기존
collection_weight_enabled: false

# 변경
collection_weight_enabled: false  # 기본값 (환경별 설정: environments/*.yaml에서 오버라이드)

# 기존
file_type_weight_enabled: false

# 변경
file_type_weight_enabled: false  # 기본값 (환경별 설정: environments/*.yaml에서 오버라이드)
```

**Step 3: Commit**

```bash
git add app/config/features/reranking.yaml app/config/features/rag.yaml
git commit -m "문서: 환경별 설정 오버라이드 주석 추가"
```

---

### Task 5: 전체 테스트 및 최종 검증

**Step 1: 전체 테스트 실행**

```bash
uv run pytest tests/ --tb=short -q
```

Expected: 모든 테스트 통과

**Step 2: 린트 및 타입 체크**

```bash
make lint && make type-check
```

Expected: All checks passed

**Step 3: 최종 커밋**

```bash
git add -A
git commit -m "완료: 환경별 설정 분리 (P2 항목)"
git push origin main
```

---

## 검증 체크리스트

- [ ] production.yaml에 reranking.min_score: 0.05 설정됨
- [ ] production.yaml에 scoring 가중치 활성화됨
- [ ] development.yaml에 개발 환경 설정 추가됨
- [ ] test.yaml에 테스트 환경 설정 추가됨
- [ ] 환경별 설정 테스트 통과
- [ ] 전체 테스트 통과 (1,700+)
- [ ] 린트/타입 체크 통과
