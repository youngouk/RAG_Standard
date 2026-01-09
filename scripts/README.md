# Scripts 디렉토리

프로젝트 관리 및 분석 스크립트 모음

## 📊 의존성 그래프 생성 (`generate_dependency_graph.py`)

pydeps를 사용하여 프로젝트의 의존성 그래프를 시각화합니다.

### 사전 준비

#### 1. Python 의존성 설치
```bash
make install-dev
# 또는
uv sync
```

#### 2. Graphviz 설치 (필수)
```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows (Chocolatey)
choco install graphviz

# 설치 확인
dot -V
```

### 기본 사용법

#### 1. 전체 프로젝트 그래프 생성 (기본값)
```bash
python scripts/generate_dependency_graph.py
```
- **출력**: `docs/diagrams/dependencies.svg`
- **형식**: SVG (확대/축소 가능)
- **깊이**: 2단계
- **클러스터링**: 활성화

#### 2. Makefile 사용 (권장)
```bash
make deps-graph
```

### 고급 사용법

#### 특정 모듈만 분석
```bash
# Retrieval 모듈만 분석
python scripts/generate_dependency_graph.py --module app.modules.core.retrieval

# API 레이어만 분석
python scripts/generate_dependency_graph.py --module app.api
```

#### 출력 형식 변경
```bash
# PNG 형식
python scripts/generate_dependency_graph.py --format png

# PDF 형식
python scripts/generate_dependency_graph.py --format pdf

# 커스텀 출력 경로
python scripts/generate_dependency_graph.py --output custom/path/graph.svg
```

#### 깊이 조절
```bash
# 1단계만 (직접 의존성만)
python scripts/generate_dependency_graph.py --max-depth 1

# 3단계까지
python scripts/generate_dependency_graph.py --max-depth 3
```

#### 클러스터링 제거 (간단한 그래프)
```bash
python scripts/generate_dependency_graph.py --no-cluster
```

#### 그래프 방향 변경
```bash
# 왼쪽에서 오른쪽 (수평)
python scripts/generate_dependency_graph.py --rankdir LR

# 오른쪽에서 왼쪽
python scripts/generate_dependency_graph.py --rankdir RL

# 아래에서 위
python scripts/generate_dependency_graph.py --rankdir BT
```

#### 특정 모듈 제외
```bash
# tests와 scripts 제외
python scripts/generate_dependency_graph.py --exclude "tests,scripts"
```

#### 외부 의존성 표시
```bash
# site-packages의 외부 라이브러리도 표시
python scripts/generate_dependency_graph.py --show-deps
```

### 조합 예시

#### 1. API 레이어 상세 분석 (PNG)
```bash
python scripts/generate_dependency_graph.py \
  --module app.api \
  --format png \
  --max-depth 3 \
  --no-cluster \
  --output docs/diagrams/api_dependencies.png
```

#### 2. Retrieval 시스템 수평 그래프
```bash
python scripts/generate_dependency_graph.py \
  --module app.modules.core.retrieval \
  --rankdir LR \
  --max-depth 2 \
  --output docs/diagrams/retrieval_flow.svg
```

#### 3. 전체 시스템 단순화 (1단계만)
```bash
python scripts/generate_dependency_graph.py \
  --max-depth 1 \
  --no-cluster \
  --exclude "tests,scripts" \
  --output docs/diagrams/overview.svg
```

#### 4. Dry Run (명령어 확인만)
```bash
python scripts/generate_dependency_graph.py --dry-run --verbose
```

### 옵션 전체 목록

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--module` | `app` | 분석할 모듈 경로 |
| `--output` | `docs/diagrams/dependencies.{format}` | 출력 파일 경로 |
| `--format` | `svg` | 출력 형식 (svg, png, pdf) |
| `--max-depth` | `2` | 최대 의존성 깊이 |
| `--no-cluster` | `False` | 클러스터링 비활성화 |
| `--rankdir` | `TB` | 그래프 방향 (TB, LR, BT, RL) |
| `--no-config` | `False` | `.pydeps` 파일 무시 |
| `--show-deps` | `False` | 외부 의존성 표시 |
| `--exclude` | `""` | 제외할 모듈 (쉼표 구분) |
| `--verbose` | `False` | 상세 출력 모드 |
| `--dry-run` | `False` | 명령어만 출력 (실행 X) |

### 그래프 해석 가이드

#### 화살표 의미
- **A → B**: A가 B를 import함
- **색상 클러스터**: 같은 패키지/모듈 그룹
- **점선**: 선택적 의존성 (일부 경우에만 import)

#### 문제 패턴 식별
1. **순환 참조**: A → B → C → A 형태의 사이클
2. **과도한 결합**: 한 모듈이 너무 많은 모듈에 의존
3. **계층 위반**: 하위 레이어가 상위 레이어를 import

### 문제 해결

#### "pydeps를 찾을 수 없습니다"
```bash
make install-dev
# 또는
uv sync
```

#### "dot 명령을 찾을 수 없습니다"
```bash
# Graphviz가 설치되지 않음
brew install graphviz  # macOS
```

#### "ImportError" 발생
```bash
# 프로젝트 루트에서 실행하는지 확인
pwd
# /Users/youngouksong/Development/MW_RAGchat

# Python 경로 확인
uv run python -c "import sys; print(sys.path)"
```

#### 그래프가 너무 복잡함
```bash
# 깊이를 1로 줄이고 클러스터링 제거
python scripts/generate_dependency_graph.py --max-depth 1 --no-cluster
```

### CI/CD 통합

#### GitHub Actions 예시
```yaml
- name: Generate Dependency Graph
  run: |
    uv sync
    python scripts/generate_dependency_graph.py --format png

- name: Upload Artifact
  uses: actions/upload-artifact@v3
  with:
    name: dependency-graph
    path: docs/diagrams/dependencies.png
```

### 참고 자료

- [pydeps 공식 문서](https://github.com/thebjorn/pydeps)
- [Graphviz 문법](https://graphviz.org/doc/info/lang.html)
- 프로젝트 의존성 규칙: `.import-linter.ini`
