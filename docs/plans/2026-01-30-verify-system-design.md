# OneRAG 검증 시스템 설계 (Verify System Design)

**날짜**: 2026-01-30
**버전**: 1.0
**상태**: 승인됨

## 1. 개요

OneRAG 오픈소스 릴리즈 전, 전체 시스템을 포괄적으로 검증하는 자동화 시스템.
Claude Code 스킬 기반으로 `/verify` 슬래시 명령어 하나로 실행.

### 1.1 검증 범위

| 영역 | 설명 |
|------|------|
| API 검증 | 엔드포인트, 스키마, SSE, WebSocket, 인증 |
| 보안 검증 | PII, 인증 우회, 환경 변수 노출, 취약점 |
| 설정 일관성 | YAML-코드 동기화, 환경별 설정, Pydantic 검증 |
| 테스트 품질 | 테스트 실행, 커버리지, 누락 모듈, Flaky 탐지 |
| 문서 동기화 | README-코드 일치, 한/영 동기화, API 가이드 |
| 빌드/CI | Docker, CI 파이프라인, lint, 타입 체크, Import 계층 |

### 1.2 산출물

- 7개 Claude 스킬 (1 오케스트레이터 + 6 서브에이전트)
- `/verify` 슬래시 명령어
- `docs/verification-report.md` 자동 생성 리포트

## 2. 아키텍처

```
/verify 실행
    │
    ▼
┌─────────────────────────────────────┐
│  Orchestrator (verify-orchestrator)  │
│  1. 프로젝트 분석                     │
│  2. 전제 조건 체크 (Docker 등)        │
│  3. Wave 1: 정적 분석 4개 (병렬)      │
│  4. Wave 2: 실행 기반 2개 (순차)      │
│  5. 에러 처리 + 결과 수집             │
│  6. 통합 리포트 생성                  │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
  Wave 1        Wave 2
  (병렬)        (순차)
┌────┬────┬────┬────┐  ┌──────┬──────┐
│API │보안│설정│문서│  │테스트│ 빌드 │
└────┴────┴────┴────┘  └──────┴──────┘
  정적 분석 전용         명령어 실행 포함
```

### 2.1 Wave 분리 이유

- **Wave 1** (API, 보안, 설정, 문서): 코드 읽기/검색만 수행. 파일시스템 충돌 없음.
- **Wave 2** (테스트, 빌드): `pytest`, `ruff`, `mypy`, `docker build` 등 실행. 동일 `.venv` 접근 충돌 방지를 위해 순차 실행.

### 2.2 서브에이전트 디스패치 방식

- Task tool의 `subagent_type: "general-purpose"` 사용
- Wave 1: `run_in_background: true`로 4개 병렬 실행
- Wave 2: 순차 실행 (verify-tests → verify-build)
- 각 서브에이전트 `max_turns: 15` 제한 (토큰 효율성)

## 3. Ralph 정신 프로토콜

실제 Ralph Wiggum은 외부에서 동일 프롬프트를 반복 주입하는 방식이지만,
Task tool 서브에이전트는 단일 세션이므로, **자기참조 반복 검증** 방식을 적용.

### 3.1 동작 방식

```
서브에이전트 진입
    │
    ▼
Phase 1: 탐색 (Discovery)
  Glob/Grep/Read로 관련 파일 수집
  → 검증 대상 목록 생성
    │
    ▼
Phase 2: 검증 루프 (Ralph-Spirit Loop)
  round = 1, consecutive_zero = 0

  while round <= 5 AND consecutive_zero < 2:
    findings = 검증_항목_실행(round)
    if findings == 0:
      consecutive_zero += 1
    else:
      consecutive_zero = 0  # 리셋
      # 발견 항목에서 파생된 새 검사 추가
    round += 1
    │
    ▼
Phase 3: 리포트 생성
  발견 목록을 심각도별 정렬
  → JSON 형태로 반환
```

### 3.2 종료 조건

| 조건 | 동작 |
|------|------|
| 연속 2회전 새 발견 0건 | 정상 종료 |
| 최대 5회전 도달 | 강제 종료 |
| Critical 10건 이상 | 조기 종료 (리포트 우선) |

### 3.3 연쇄 발견 원리

```
예시: verify-config

1회전: base.yaml에 "reranker_timeout" 키 존재, 코드에서 미참조 → Warning
2회전: 미참조 키를 추적 → production.yaml의 "cache_ttl"이 코드에서
       "cache_timeout"으로 참조되는 불일치 발견 → Critical
3회전: 키 불일치를 추적 → test.yaml에 캐시 설정 자체가 누락 → Warning
4회전: 추가 발견 없음 → consecutive_zero = 1
5회전: 추가 발견 없음 → consecutive_zero = 2 → 종료
```

## 4. 검증 항목 상세 (42개)

### 4.1 verify-api (7개)

1. **엔드포인트 존재 확인**: 라우터 등록 경로와 실제 핸들러 매핑 일치
2. **스키마 일관성**: Pydantic 모델의 필드와 실제 응답 구조 비교
3. **SSE 스트리밍**: /chat/stream 이벤트 타입(metadata, chunk, done, error) 형식
4. **WebSocket 프로토콜**: /chat-ws 메시지 타입 준수 여부
5. **Rate Limit**: rate_limiter.py 설정값과 라우터 적용 일치
6. **에러 응답**: ErrorCode 기반 양언어 에러가 모든 엔드포인트에 적용
7. **Admin 인증**: /api/admin/** 경로 X-API-Key 인증 누락 검사

### 4.2 verify-security (7개)

1. **PII 마스킹**: 한국어 주민번호, 전화번호, 이메일 패턴 처리 범위
2. **인증 우회**: Admin API 인증 없이 접근 가능한 경로 탐색
3. **환경 변수 노출**: .env, API 키가 로그/응답에 노출 여부
4. **의존성 취약점**: pyproject.toml 패키지 알려진 CVE 존재 여부
5. **Injection 방어**: 쿼리 파라미터 직접 DB 삽입 코드 탐색
6. **CORS 설정**: 허용 origin 과도 개방 여부
7. **Prompt Injection**: prompt_sanitizer.py 방어 범위 확인

### 4.3 verify-config (7개)

1. **YAML-코드 동기화**: base.yaml 키와 코드 참조 설정 키 일치
2. **환경별 분리**: development/test/production.yaml 누락 키
3. **Pydantic 검증**: 스키마 범위와 실제 YAML 값 비교
4. **환경 변수 매핑**: .env.quickstart 변수와 코드 사용 일치
5. **Docker 설정**: docker-compose.yml 환경 변수와 .env 템플릿 일치
6. **Reranker 설정**: approach/provider/model 조합 유효성
7. **Vector DB 설정**: 6종 벡터 DB 필수 환경 변수 문서화

### 4.4 verify-tests (7개)

1. **테스트 실행**: `pytest` 전체 통과 확인
2. **커버리지 분석**: 80% 미달 모듈 식별
3. **테스트 누락**: app/ 모듈 중 대응 테스트 파일 없는 모듈
4. **마커 일관성**: @pytest.mark 올바른 사용 여부
5. **Mock 품질**: Mock이 Protocol 인터페이스와 일치하는지
6. **비동기 테스트**: async 테스트 누락 확인
7. **Flaky 탐지**: 타임아웃/경쟁 조건 취약 패턴

### 4.5 verify-docs (7개)

1. **README vs 코드**: 설치 명령어, API 예시 일치
2. **CLAUDE.md 정확성**: 버전, 테스트 수, 기능 목록 현재 상태 반영
3. **API 가이드**: streaming/websocket 가이드 내용 검증
4. **한/영 동기화**: README.md와 README_EN.md 내용 일치
5. **아키텍처 문서**: ARCHITECTURE.md Mermaid 다이어그램 정확성
6. **Quickstart**: quickstart/ 실행 흐름 실제 동작 일치
7. **CHANGELOG**: 최근 변경사항 문서 반영 여부

### 4.6 verify-build (7개)

1. **Docker 빌드**: Dockerfile 정상 빌드 (Docker 미실행 시 건너뜀)
2. **CI 파이프라인**: .github/workflows/ 설정 유효성
3. **uv.lock 동기화**: pyproject.toml과 uv.lock 일치
4. **린트 통과**: `ruff check` 성공
5. **타입 체크**: `mypy --strict` 통과
6. **Import 계층**: import-linter 통과
7. **Makefile 검증**: 주요 make 타겟 실행 가능 여부

## 5. 에러 처리

### 5.1 서브에이전트 실패

| 상황 | 대응 |
|------|------|
| 타임아웃 (300초) | 리포트에 "⚠️ 검증 미완료" 표시, 나머지 정상 수집 |
| 토큰 한계 도달 | 해당 시점까지 수집된 결과로 부분 리포트 |
| 파일 접근 실패 | 해당 항목 건너뛰고 Info로 기록 |

### 5.2 전제 조건 미충족

| 전제 조건 | 미충족 시 |
|-----------|----------|
| Docker 미실행 | verify-build Docker 항목 건너뜀 (Info) |
| .venv 미존재 | verify-tests/build에서 uv sync 시도 |
| Git 미초기화 | verify-docs CHANGELOG 항목 건너뜀 |

## 6. 리포트 형식

### 6.1 통합 리포트 (docs/verification-report.md)

```markdown
# OneRAG 검증 리포트
**일시**: 2026-01-30 12:00
**프로젝트 버전**: 1.2.1
**검증 도메인**: 6/6 완료

## 요약
| 심각도 | 건수 |
|--------|------|
| Critical | 2 |
| Warning | 5 |
| Info | 8 |

## Critical 항목
### [API] SSE 이벤트 형식 불일치
- **파일**: app/api/chat.py:145
- **설명**: done 이벤트에 total_chunks 필드 누락
- **수정안**: StreamDoneEvent 모델에 total_chunks 필드 추가

## Warning 항목
...

## Info 항목
...

## 도메인별 상세
### API 검증 (3라운드, 2분 12초)
...
```

### 6.2 서브에이전트 반환 형식 (JSON)

```json
{
  "domain": "api",
  "rounds": 3,
  "findings": [
    {
      "severity": "critical",
      "item": "SSE 이벤트 형식 불일치",
      "file": "app/api/chat.py:145",
      "description": "done 이벤트에 total_chunks 필드가 누락됨",
      "suggestion": "StreamDoneEvent 모델에 total_chunks 필드 추가"
    }
  ],
  "summary": { "critical": 1, "warning": 2, "info": 3 }
}
```

## 7. 스킬 파일 구조

```
~/.claude/skills/
├── verify-orchestrator/SKILL.md    ← /verify 명령어
├── verify-api/SKILL.md             ← API 검증
├── verify-security/SKILL.md        ← 보안 검증
├── verify-config/SKILL.md          ← 설정 검증
├── verify-tests/SKILL.md           ← 테스트 검증
├── verify-docs/SKILL.md            ← 문서 검증
└── verify-build/SKILL.md           ← 빌드 검증
```

## 8. 구현 순서

1. 설계 문서 작성 (본 문서)
2. verify-orchestrator 스킬 생성
3. 6개 서브에이전트 스킬 생성
4. Git 커밋
