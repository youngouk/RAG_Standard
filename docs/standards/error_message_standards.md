# 에러 메시지 표준 가이드라인

**버전**: 1.0
**작성일**: 2026-01-08
**목적**: RAG_Standard 프로젝트 전반의 사용자 친화적이고 실행 가능한 에러 메시지 작성 표준 정의

---

## 📋 목차
1. [에러 메시지 구조](#에러-메시지-구조)
2. [카테고리별 예시](#카테고리별-예시)
3. [권장 패턴](#권장-패턴)
4. [지양 패턴](#지양-패턴)
5. [코드 예시](#코드-예시)

---

## 에러 메시지 구조

### 기본 구조
모든 에러 메시지는 다음 3가지 요소를 포함해야 합니다:

```
[문제 설명] + [원인 추정] + [해결 방법]
```

---

### 1. 문제 설명 (What)
**목적**: 무엇이 잘못되었는지 명확히 전달

**원칙**:
- 구체적이고 간결하게
- 기술 용어와 일반 용어 병기
- 사용자가 이해할 수 있는 언어 사용

**예시**:
```
✅ "Weaviate 벡터 데이터베이스 연결 실패"
❌ "연결 오류"
```

---

### 2. 원인 추정 (Why)
**목적**: 왜 문제가 발생했는지 가능성 있는 원인 제시

**원칙**:
- 가장 가능성 높은 원인부터 나열
- 확실하지 않을 때는 "가능성" 명시
- 기술적 세부사항 포함 (디버깅 용이)

**예시**:
```
✅ "네트워크 오류 또는 Weaviate 서버 미실행 상태입니다"
❌ "뭔가 잘못되었습니다"
```

---

### 3. 해결 방법 (How)
**목적**: 사용자가 직접 문제를 해결할 수 있도록 구체적인 단계 제시

**원칙**:
- 실행 가능한 단계별 가이드
- 명령어 예시 포함
- 관련 문서 링크 제공
- 긴급도 순서로 정렬

**예시**:
```
✅ "1. docker-compose.weaviate.yml이 실행 중인지 확인하세요 (docker ps)
    2. WEAVIATE_URL 환경 변수가 올바른지 확인하세요
    3. 네트워크 연결 상태를 확인하세요"
❌ "설정을 확인하세요"
```

---

## 카테고리별 예시

### 1. 연결 실패 (Connection Errors)

#### Weaviate 연결 실패
```python
error_message = (
    "Weaviate 벡터 데이터베이스 연결 실패. "
    "네트워크 오류 또는 Weaviate 서버 미실행 상태입니다. "
    "1. docker-compose.weaviate.yml이 실행 중인지 확인하세요 (docker ps)\n"
    "2. WEAVIATE_URL 환경 변수가 올바른지 확인하세요\n"
    "3. 네트워크 연결 상태를 확인하세요"
)
```

#### MongoDB 연결 실패
```python
error_message = (
    "MongoDB 세션 저장소 연결 실패. "
    "잘못된 URI 형식이거나 MongoDB 서버가 응답하지 않습니다. "
    "1. MONGODB_URI 환경 변수가 올바른 형식인지 확인하세요\n"
    "   예시: mongodb+srv://user:password@cluster.mongodb.net/database\n"
    "2. 네트워크 방화벽이 MongoDB 포트(27017)를 차단하지 않는지 확인하세요\n"
    "3. MongoDB Atlas의 경우 IP 화이트리스트를 확인하세요"
)
```

#### Redis 연결 실패
```python
error_message = (
    "Redis 캐시 서버 연결 실패. "
    "Redis 서버가 실행 중이지 않거나 연결 설정이 잘못되었습니다. "
    "1. Redis가 실행 중인지 확인하세요 (redis-cli ping)\n"
    "2. REDIS_URL 환경 변수가 올바른지 확인하세요\n"
    "   예시: redis://localhost:6379\n"
    "3. 로컬 개발 환경이면 'docker-compose up redis'를 실행하세요"
)
```

---

### 2. 설정 오류 (Configuration Errors)

#### 설정 파일 로드 실패
```python
error_message = (
    f"설정 파일 로드 실패: {config_path}. "
    f"파일이 존재하지 않거나 YAML 형식이 잘못되었습니다. "
    f"1. 파일 경로가 올바른지 확인하세요: {config_path}\n"
    f"2. YAML 형식 검증기로 구문 오류를 확인하세요: https://yamlchecker.com/\n"
    f"3. 예시 설정 파일을 참고하세요: app/config/base.yaml"
)
```

#### 필수 설정 값 누락
```python
error_message = (
    f"필수 설정 값 누락: {missing_key}. "
    f"설정 파일에 필수 키가 없습니다. "
    f"1. app/config/base.yaml에 '{missing_key}' 키를 추가하세요\n"
    f"2. 설정 스키마를 확인하세요: docs/config/schema.md\n"
    f"3. 기본값이 필요하면 .env.example을 참고하세요"
)
```

#### 잘못된 설정 값
```python
error_message = (
    f"잘못된 설정 값: {key}={value}. "
    f"유효 범위를 벗어났거나 지원하지 않는 값입니다. "
    f"1. 유효한 값: {valid_values}\n"
    f"2. 현재 값: {value}\n"
    f"3. 설정 가이드를 참고하세요: docs/config/guide.md"
)
```

---

### 3. API 키 관련 (API Key Errors)

#### API 키 누락
```python
error_message = (
    "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
    "Gemini API를 사용하려면 API 키가 필요합니다. "
    "1. .env 파일에 'GOOGLE_API_KEY=AIza...'를 추가하세요\n"
    "2. API 키 발급: https://makersuite.google.com/app/apikey\n"
    "3. .env.example 파일을 참고하세요"
)
```

#### 잘못된 API 키
```python
error_message = (
    "GOOGLE_API_KEY가 유효하지 않습니다. "
    "API 키 형식이 잘못되었거나 만료되었습니다. "
    "1. API 키가 'AIza'로 시작하는지 확인하세요\n"
    "2. Google Cloud Console에서 API 키 상태를 확인하세요\n"
    "3. 새 API 키를 발급받으세요: https://makersuite.google.com/app/apikey"
)
```

#### API 할당량 초과
```python
error_message = (
    "Google API 할당량 초과. "
    "하루 허용량을 초과했거나 분당 요청 수 제한에 도달했습니다. "
    "1. Google Cloud Console에서 할당량을 확인하세요\n"
    "2. 잠시 후 다시 시도하세요 (분당 제한: 60회)\n"
    "3. 할당량 증가 요청: https://cloud.google.com/apis/docs/quota"
)
```

---

### 4. 데이터 검증 오류 (Validation Errors)

#### 필수 필드 누락
```python
error_message = (
    f"필수 필드 누락: {field_name}. "
    f"요청 데이터에 필수 필드가 포함되지 않았습니다. "
    f"1. 요청 본문에 '{field_name}' 필드를 추가하세요\n"
    f"2. API 스키마를 확인하세요: /docs (Swagger UI)\n"
    f"3. 올바른 요청 예시:\n{example_request}"
)
```

#### 잘못된 데이터 형식
```python
error_message = (
    f"잘못된 데이터 형식: {field_name}. "
    f"예상: {expected_type}, 실제: {actual_type}. "
    f"1. '{field_name}' 필드의 데이터 타입을 확인하세요\n"
    f"2. 올바른 형식: {expected_type}\n"
    f"3. 제공된 값: {actual_value} ({actual_type})"
)
```

#### 값 범위 초과
```python
error_message = (
    f"값 범위 초과: {field_name}={value}. "
    f"허용 범위: {min_value} ~ {max_value}. "
    f"1. 값을 허용 범위 내로 조정하세요\n"
    f"2. 현재 값: {value}\n"
    f"3. 권장 값: {recommended_value}"
)
```

---

### 5. 권한 오류 (Permission Errors)

#### 인증 실패
```python
error_message = (
    "API 인증 실패. "
    "X-API-Key 헤더가 없거나 유효하지 않습니다. "
    "1. 요청 헤더에 'X-API-Key: <your-key>'를 추가하세요\n"
    "2. .env 파일의 FASTAPI_AUTH_KEY와 일치하는지 확인하세요\n"
    "3. API 키 발급: 시스템 관리자에게 문의하세요"
)
```

#### 권한 부족
```python
error_message = (
    "권한 부족. "
    "이 작업을 수행할 권한이 없습니다. "
    "1. 관리자 권한이 필요한 작업입니다\n"
    "2. 계정 권한을 확인하세요\n"
    "3. 관리자에게 권한 승인을 요청하세요"
)
```

---

### 6. 리소스 오류 (Resource Errors)

#### 리소스 없음
```python
error_message = (
    f"리소스를 찾을 수 없음: {resource_type} ID={resource_id}. "
    f"요청한 리소스가 존재하지 않거나 삭제되었습니다. "
    f"1. ID가 올바른지 확인하세요: {resource_id}\n"
    f"2. 리소스 목록을 조회하세요: GET /api/{resource_type}\n"
    f"3. 리소스가 최근 삭제되었는지 확인하세요"
)
```

#### 리소스 충돌
```python
error_message = (
    f"리소스 충돌: {resource_type} '{identifier}'가 이미 존재합니다. "
    f"동일한 식별자를 가진 리소스가 이미 등록되어 있습니다. "
    f"1. 다른 식별자를 사용하세요\n"
    f"2. 기존 리소스를 수정하려면 PUT /api/{resource_type}/{id}를 사용하세요\n"
    f"3. 기존 리소스를 조회하세요: GET /api/{resource_type}?name={identifier}"
)
```

---

### 7. 시스템 오류 (System Errors)

#### 타임아웃
```python
error_message = (
    f"작업 타임아웃: {operation_name}. "
    f"작업이 {timeout_seconds}초 이내에 완료되지 않았습니다. "
    f"1. 네트워크 연결 상태를 확인하세요\n"
    f"2. 서버 부하가 높은지 확인하세요\n"
    f"3. AGENT_TIMEOUT_SECONDS 환경 변수를 늘려보세요 (현재: {timeout_seconds}초)"
)
```

#### 메모리 부족
```python
error_message = (
    "메모리 부족. "
    "처리할 데이터가 너무 크거나 시스템 리소스가 부족합니다. "
    "1. 요청 데이터 크기를 줄이세요\n"
    "2. 배치 처리를 사용하세요 (한 번에 작은 단위로 처리)\n"
    "3. 시스템 메모리를 확인하세요: free -h"
)
```

---

## 권장 패턴

### ✅ 패턴 1: 구체적이고 실행 가능한 메시지

```python
# ✅ 좋은 예
raise ValueError(
    "WEAVIATE_URL 환경 변수가 설정되지 않았습니다. "
    ".env 파일에 'WEAVIATE_URL=http://localhost:8080'을 추가하세요. "
    "로컬 개발: docker-compose.weaviate.yml을 실행하세요."
)

# ❌ 나쁜 예
raise ValueError("Weaviate URL이 없습니다")
```

---

### ✅ 패턴 2: 원인과 해결 방법 명시

```python
# ✅ 좋은 예
raise ConfigError(
    f"설정 파일 파싱 실패: {config_path}. "
    f"YAML 형식이 잘못되었습니다: {yaml_error}. "
    f"온라인 YAML 검증기로 확인하세요: https://yamlchecker.com/"
)

# ❌ 나쁜 예
raise ConfigError("설정 파일 오류")
```

---

### ✅ 패턴 3: 예시 포함

```python
# ✅ 좋은 예
raise ValueError(
    "MONGODB_URI 형식이 잘못되었습니다. "
    "올바른 형식: mongodb+srv://user:password@cluster.mongodb.net/database. "
    f"현재 값: {mongodb_uri}"
)

# ❌ 나쁜 예
raise ValueError("MongoDB URI 형식 오류")
```

---

### ✅ 패턴 4: 단계별 가이드

```python
# ✅ 좋은 예
raise RuntimeError(
    "Weaviate 스키마 생성 실패. "
    "클래스가 이미 존재하거나 스키마 형식이 잘못되었습니다. "
    "1. 기존 스키마를 삭제하세요: DELETE /v1/schema/Document\n"
    "2. 스키마 형식을 확인하세요: docs/weaviate/schema.json\n"
    "3. 스키마를 다시 생성하세요: python scripts/init_weaviate.py"
)

# ❌ 나쁜 예
raise RuntimeError("스키마 생성 실패")
```

---

## 지양 패턴

### ❌ 패턴 1: 애매한 메시지

```python
# ❌ 나쁜 예
raise Exception("오류 발생")
raise ValueError("잘못된 값")
raise RuntimeError("실패")

# ✅ 좋은 예
raise ValueError(
    "AGENT_TIMEOUT_SECONDS 값이 유효하지 않습니다: {value}. "
    "양의 정수여야 합니다 (최소: 10, 최대: 3600). "
    ".env 파일에서 'AGENT_TIMEOUT_SECONDS=300'과 같이 설정하세요."
)
```

---

### ❌ 패턴 2: 기술 용어만 사용

```python
# ❌ 나쁜 예
raise ConnectionError("gRPC call failed: UNAVAILABLE")

# ✅ 좋은 예
raise ConnectionError(
    "Weaviate gRPC 연결 실패 (UNAVAILABLE). "
    "Weaviate 서버가 응답하지 않거나 gRPC 포트가 닫혀있습니다. "
    "1. Weaviate가 실행 중인지 확인하세요: docker ps\n"
    "2. gRPC 포트가 열려있는지 확인하세요: WEAVIATE_GRPC_PORT=50051\n"
    "3. 방화벽이 포트를 차단하지 않는지 확인하세요"
)
```

---

### ❌ 패턴 3: 해결 방법 없음

```python
# ❌ 나쁜 예
raise RuntimeError("MongoDB 연결 실패")

# ✅ 좋은 예
raise RuntimeError(
    "MongoDB 연결 실패. "
    "네트워크 오류 또는 잘못된 URI입니다. "
    "1. MONGODB_URI 환경 변수를 확인하세요\n"
    "2. MongoDB Atlas IP 화이트리스트를 확인하세요\n"
    "3. 네트워크 연결을 테스트하세요: telnet <host> 27017"
)
```

---

## 코드 예시

### 예시 1: Weaviate 클라이언트 초기화

```python
from weaviate import WeaviateClient
from weaviate.auth import AuthApiKey

def create_weaviate_client(url: str, api_key: str | None = None) -> WeaviateClient:
    """Weaviate 클라이언트 생성

    Args:
        url: Weaviate 서버 URL
        api_key: API 키 (선택사항)

    Returns:
        WeaviateClient 인스턴스

    Raises:
        ValueError: URL이 유효하지 않을 때
        ConnectionError: Weaviate 서버 연결 실패 시
    """
    # URL 검증
    if not url:
        raise ValueError(
            "WEAVIATE_URL 환경 변수가 설정되지 않았습니다. "
            ".env 파일에 'WEAVIATE_URL=http://localhost:8080'을 추가하세요. "
            "로컬 개발 환경이면 'docker-compose.weaviate.yml'을 실행하세요."
        )

    if not url.startswith(("http://", "https://")):
        raise ValueError(
            f"WEAVIATE_URL 형식이 잘못되었습니다: {url}. "
            f"http:// 또는 https://로 시작해야 합니다. "
            f"올바른 예시:\n"
            f"  - 로컬: http://localhost:8080\n"
            f"  - 프로덕션: https://your-cluster.weaviate.cloud"
        )

    # 연결 시도
    try:
        client = WeaviateClient(
            url=url,
            auth_client_secret=AuthApiKey(api_key) if api_key else None
        )
        client.is_ready()  # 연결 테스트
        return client

    except Exception as e:
        raise ConnectionError(
            f"Weaviate 연결 실패: {url}. "
            f"네트워크 오류 또는 Weaviate 서버 미실행 상태입니다. "
            f"1. Weaviate가 실행 중인지 확인하세요: docker ps | grep weaviate\n"
            f"2. URL이 올바른지 확인하세요: {url}\n"
            f"3. 네트워크 연결을 테스트하세요: curl {url}/v1/.well-known/ready\n"
            f"에러 상세: {type(e).__name__}: {str(e)}"
        ) from e
```

---

### 예시 2: 설정 파일 로드

```python
import yaml
from pathlib import Path

def load_yaml_config(config_path: str) -> dict:
    """YAML 설정 파일 로드

    Args:
        config_path: 설정 파일 경로

    Returns:
        설정 딕셔너리

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        yaml.YAMLError: YAML 파싱 실패 시
    """
    path = Path(config_path)

    # 파일 존재 확인
    if not path.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없음: {config_path}. "
            f"파일이 존재하지 않습니다. "
            f"1. 파일 경로가 올바른지 확인하세요\n"
            f"2. 현재 디렉토리: {Path.cwd()}\n"
            f"3. 예시 설정 파일을 복사하세요: cp app/config/base.yaml.example {config_path}"
        )

    # YAML 파싱
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise yaml.YAMLError(
                f"설정 파일은 딕셔너리 형태여야 합니다. "
                f"현재 타입: {type(config).__name__}"
            )

        return config

    except yaml.YAMLError as e:
        raise yaml.YAMLError(
            f"설정 파일 파싱 실패: {config_path}. "
            f"YAML 형식이 잘못되었습니다. "
            f"1. YAML 문법을 확인하세요: https://yamlchecker.com/\n"
            f"2. 인덴트가 올바른지 확인하세요 (스페이스 2칸 권장)\n"
            f"3. 예시 파일을 참고하세요: app/config/base.yaml.example\n"
            f"에러 상세: {str(e)}"
        ) from e
```

---

### 예시 3: API 키 검증

```python
import os
import re

def get_google_api_key() -> str:
    """Google API 키 가져오기

    Returns:
        Google API 키

    Raises:
        ValueError: API 키가 없거나 형식이 잘못되었을 때
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    # 키 존재 확인
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
            "Gemini API를 사용하려면 API 키가 필요합니다. "
            "1. .env 파일에 'GOOGLE_API_KEY=AIza...'를 추가하세요\n"
            "2. API 키 발급: https://makersuite.google.com/app/apikey\n"
            "3. .env.example 파일을 참고하세요"
        )

    # 키 형식 검증
    if not re.match(r"^AIza[0-9A-Za-z_-]{35}$", api_key):
        raise ValueError(
            f"GOOGLE_API_KEY 형식이 유효하지 않습니다. "
            f"Google API 키는 'AIza'로 시작하고 39자여야 합니다. "
            f"1. 키를 다시 복사하세요 (공백 제거)\n"
            f"2. Google Cloud Console에서 키를 확인하세요\n"
            f"3. 새 키를 발급받으세요: https://makersuite.google.com/app/apikey\n"
            f"현재 키 길이: {len(api_key)}자"
        )

    return api_key
```

---

## 체크리스트

에러 메시지 작성 시 다음을 확인하세요:

- [ ] 문제 설명: 무엇이 잘못되었는지 명확히 서술
- [ ] 원인 추정: 왜 문제가 발생했는지 가능성 제시
- [ ] 해결 방법: 구체적인 단계별 가이드 제공
- [ ] 예시 포함: 올바른 형식이나 명령어 예시
- [ ] 관련 링크: 문서, 가이드, 발급 페이지 등
- [ ] 에러 컨텍스트: 현재 값, 예상 값, 유효 범위 등
- [ ] 사용자 친화적: 기술 용어와 일반 용어 병기

---

**참고 문서**:
- [로그 메시지 표준](./logging_standards.md)
- [Python Exception Handling](https://docs.python.org/3/tutorial/errors.html)
- [Error Message Design](https://www.nngroup.com/articles/error-message-guidelines/)
