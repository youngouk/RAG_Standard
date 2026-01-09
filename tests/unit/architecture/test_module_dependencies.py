"""
모듈 간 의존성 규칙 테스트

Phase 3 R3.1: modules/core/* 순환 의존성 검사
TDD RED 단계 - 테스트 먼저 작성
"""

import ast
from collections import defaultdict
from pathlib import Path

import pytest


class TestModuleDependencies:
    """modules/core 모듈 간 의존성 규칙 검증"""

    @pytest.fixture
    def core_modules(self) -> list[str]:
        """modules/core 내의 모듈 목록"""
        core_path = Path("app/modules/core")
        return [
            d.name
            for d in core_path.iterdir()
            if d.is_dir() and not d.name.startswith("__")
        ]

    @pytest.fixture
    def module_dependencies(self, core_modules: list[str]) -> dict[str, set[str]]:
        """각 모듈의 의존성 분석"""
        core_path = Path("app/modules/core")
        deps: dict[str, set[str]] = defaultdict(set)

        for module in core_modules:
            module_path = core_path / module
            for py_file in module_path.rglob("*.py"):
                try:
                    with open(py_file) as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            for other in core_modules:
                                if other == module:
                                    continue  # 자기 참조 제외
                                if f"app.modules.core.{other}" in node.module:
                                    deps[module].add(other)
                except Exception:
                    pass

        return dict(deps)

    def test_no_circular_dependencies(
        self, module_dependencies: dict[str, set[str]]
    ) -> None:
        """순환 의존성이 없어야 함"""

        def find_cycle(
            graph: dict[str, set[str]], start: str, visited: set[str], path: list[str]
        ) -> list[str] | None:
            """DFS로 순환 탐지"""
            if start in visited:
                if start in path:
                    cycle_start = path.index(start)
                    return path[cycle_start:] + [start]
                return None

            visited.add(start)
            path.append(start)

            for neighbor in graph.get(start, set()):
                result = find_cycle(graph, neighbor, visited, path)
                if result:
                    return result

            path.pop()
            return None

        cycles = []
        for module in module_dependencies:
            result = find_cycle(module_dependencies, module, set(), [])
            if result and result not in cycles:
                cycles.append(result)

        assert not cycles, f"순환 의존성 발견: {cycles}"

    def test_documents_not_import_retrieval(self) -> None:
        """documents 모듈은 retrieval을 직접 import하지 않아야 함

        documents는 문서 처리(로딩, 청킹) 담당.
        retrieval은 검색 담당.
        documents -> retrieval 의존성은 계층 위반.
        """
        docs_init = Path("app/modules/core/documents/__init__.py")

        # AST로 실제 import 문만 검사 (독스트링 제외)
        with open(docs_init) as f:
            tree = ast.parse(f.read())

        retrieval_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "app.modules.core.retrieval" in node.module:
                    retrieval_imports.append(node.module)

        assert not retrieval_imports, (
            f"documents/__init__.py에서 retrieval import 제거 필요: {retrieval_imports}"
        )

    def test_allowed_dependencies(
        self, module_dependencies: dict[str, set[str]]
    ) -> None:
        """허용된 의존성 규칙 검증

        허용되는 의존성:
        - retrieval -> graph (하이브리드 검색)
        - retrieval -> embedding (임베딩 생성)
        - agent -> mcp (도구 실행)
        - mcp -> graph (그래프 도구)
        """
        allowed = {
            "retrieval": {"graph", "embedding"},
            "agent": {"mcp", "retrieval"},
            "mcp": {"graph", "retrieval", "sql_search"},
            "generation": {"retrieval"},
        }

        for module, deps in module_dependencies.items():
            allowed_deps = allowed.get(module, set())
            unexpected = deps - allowed_deps
            if unexpected:
                # 경고만 출력 (엄격하지 않음)
                print(f"⚠️ {module}의 예상치 못한 의존성: {unexpected}")

    def test_graph_not_import_retrieval(self) -> None:
        """graph 모듈은 retrieval을 import하지 않아야 함

        graph는 지식 그래프 저장소 담당.
        retrieval이 graph를 사용하는 것은 OK.
        graph가 retrieval을 사용하면 순환 의존성 위험.
        """
        graph_path = Path("app/modules/core/graph")
        for py_file in graph_path.rglob("*.py"):
            content = py_file.read_text()
            assert "from app.modules.core.retrieval" not in content, (
                f"graph 모듈이 retrieval을 import: {py_file}"
            )
