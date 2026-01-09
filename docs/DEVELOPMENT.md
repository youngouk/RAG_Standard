# 개발 및 품질 가이드 (Development)

프로젝트의 코드 품질을 유지하고 협업 효율을 높이기 위한 개발 가이드라인입니다.

---

## 1. 코딩 컨벤션

### 1.1 타입 힌트 (Type Hinting)
- 모든 함수와 메서드에는 명확한 타입 힌트를 작성해야 합니다.
- **MyPy 엄격 모드** 적용: `app/modules/core/privacy`, `app/modules/core/self_rag` 등 핵심 모듈은 타입 체크를 통과해야 합니다.

### 1.2 비동기 프로그래밍
- I/O 작업(DB, API 호출)은 반드시 `async`/`await`를 사용합니다.
- 동기 라이브러리를 사용할 경우 `asyncio.to_thread` 등으로 래핑하여 이벤트 루프 블로킹을 방지합니다.

---

## 2. 도구 활용 (Makefile)

패키지 관리와 품질 검사를 위해 `make` 명령어를 제공합니다.

- `make lint`: Ruff를 이용한 코드 스타일 검사
- `make format`: 코드 자동 포맷팅
- `make type-check`: MyPy 타입 체크
- `make test`: 전체 유닛 테스트 실행

---

## 3. 테스트 가이드

### 3.1 테스트 구조
- `tests/unit`: 개별 클래스 및 함수 단위 테스트
- `tests/integration`: 컴포넌트 간 결합 및 외부 API(Mock) 테스트

### 3.2 테스트 실행 및 격리
```bash
# 전체 테스트 실행 (1080+ 테스트)
make test
```

**테스트 환경 격리 전략 (v3.3.0):**
- **Langfuse 격리**: 테스트 실행 시 `ENVIRONMENT=test` 설정을 통해 Langfuse SDK 로딩을 원천 차단합니다. 이를 통해 네트워크 연결 오류(`Connection refused`) 없이 깨끗한 테스트 로그를 유지할 수 있습니다.
- **Dependency Overrides**: FastAPI의 `dependency_overrides`를 활용하여 통합 테스트 시 인증이나 외부 서비스를 안전하게 모킹합니다.

**운영 안정성 검증:**
시스템은 다음 장애 시나리오에 대한 100% 회복력을 테스트로 증명했습니다:
- **LLM/DB 장애**: API 타임아웃 시 Fallback 체인 작동.
- **Circuit Breaker**: 연속 실패 시 장애 격리 및 자동 복구.
- **Race Condition**: 동시 세션 생성 시 데이터 일관성 유지 (asyncio.Lock).

---

## 4. 기술 부채 관리

본 프로젝트는 **기술 부채 제로(Zero TODO)**를 지향합니다.
- 새로운 `TODO`를 작성할 때는 반드시 기한과 담당자를 명시하거나, 즉시 해결을 권장합니다.
- 정적 분석(`Ruff`, `Mypy`)은 CI/CD 파이프라인에서 필수로 통과해야 합니다.
