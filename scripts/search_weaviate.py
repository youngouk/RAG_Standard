#!/usr/bin/env python3
"""
Weaviate DB 검색 스크립트

Railway에 배포된 Weaviate에서 문서를 검색하는 CLI 도구입니다.

기능:
- 텍스트 기반 검색 (Like 연산자)
- 시맨틱 검색 (벡터 유사도)
- source_file 필터링
- 결과 하이라이팅

사용 예시:
    # 텍스트 검색 (Like)
    python scripts/search_weaviate.py --query "이용요금" --mode text

    # 시맨틱 검색 (벡터)
    python scripts/search_weaviate.py --query "서비스 가격" --mode semantic

    # 특정 소스 필터링
    python scripts/search_weaviate.py --query "블랙라벨" --source notion_dress_database

    # 결과 개수 제한
    python scripts/search_weaviate.py --query "취소" --limit 10
"""

import argparse
import json
import os
import re
import sys

import requests

# Rich 라이브러리 선택적 import (없으면 기본 출력 사용)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


# 설정
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "https://weaviate-production-70aa.up.railway.app")
GRAPHQL_ENDPOINT = f"{WEAVIATE_URL}/v1/graphql"


def print_output(message: str, style: str = ""):
    """출력 래퍼 함수 (Rich 없으면 기본 print)"""
    if RICH_AVAILABLE:
        console.print(message)
    else:
        # ANSI 색상 제거
        clean_message = re.sub(r"\[.*?\]", "", message)
        print(clean_message)


def text_search(query: str, limit: int = 5, source_filter: str | None = None) -> dict:
    """
    텍스트 기반 검색 (Like 연산자)

    Args:
        query: 검색어 (와일드카드 * 자동 추가)
        limit: 최대 결과 개수
        source_filter: source_file 필터 (선택)

    Returns:
        GraphQL 응답 결과
    """
    # 와일드카드 추가
    search_pattern = f"*{query}*"

    # 기본 where 조건
    where_clause = f"""
        operator: Like
        path: ["content"]
        valueText: "{search_pattern}"
    """

    # source_file 필터 추가
    if source_filter:
        where_clause = f"""
            operator: And
            operands: [
                {{
                    operator: Like
                    path: ["content"]
                    valueText: "{search_pattern}"
                }},
                {{
                    operator: Equal
                    path: ["source_file"]
                    valueText: "{source_filter}"
                }}
            ]
        """

    graphql_query = f"""
    {{
        Get {{
            Documents(
                where: {{ {where_clause} }}
                limit: {limit}
            ) {{
                content
                source_file
                original_index
                _additional {{
                    id
                }}
            }}
        }}
    }}
    """

    return execute_query(graphql_query)


def semantic_search(query: str, limit: int = 5, source_filter: str | None = None) -> dict:
    """
    시맨틱 검색 (벡터 유사도)

    Args:
        query: 검색 텍스트
        limit: 최대 결과 개수
        source_filter: source_file 필터 (선택)

    Returns:
        GraphQL 응답 결과
    """
    # where 조건 (source_filter가 있는 경우)
    where_clause = ""
    if source_filter:
        where_clause = f"""
            where: {{
                operator: Equal
                path: ["source_file"]
                valueText: "{source_filter}"
            }}
        """

    graphql_query = f"""
    {{
        Get {{
            Documents(
                nearText: {{
                    concepts: ["{query}"]
                }}
                {where_clause}
                limit: {limit}
            ) {{
                content
                source_file
                original_index
                _additional {{
                    id
                    distance
                    certainty
                }}
            }}
        }}
    }}
    """

    return execute_query(graphql_query)


def execute_query(graphql_query: str) -> dict:
    """
    GraphQL 쿼리 실행

    Args:
        graphql_query: GraphQL 쿼리 문자열

    Returns:
        응답 JSON

    Raises:
        requests.RequestException: 네트워크 오류
        ValueError: 쿼리 오류
    """
    try:
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={"query": graphql_query},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            raise ValueError(f"GraphQL 오류: {result['errors']}")

        return result

    except requests.RequestException as e:
        print_output(f"[red]❌ 네트워크 오류: {e}[/red]")
        raise


def get_full_document(source_file: str, limit: int = 500) -> dict:
    """
    특정 source_file의 모든 청크를 순서대로 조회

    Args:
        source_file: 소스 파일명
        limit: 최대 청크 개수

    Returns:
        해당 파일의 모든 청크
    """
    graphql_query = f"""
    {{
        Get {{
            Documents(
                where: {{
                    operator: Equal
                    path: ["source_file"]
                    valueText: "{source_file}"
                }}
                limit: {limit}
            ) {{
                content
                source_file
                original_index
                _additional {{
                    id
                }}
            }}
        }}
    }}
    """

    return execute_query(graphql_query)


def display_full_document(source_file: str, limit: int = 500):
    """전체 문서 내용 출력"""
    print_output(f"\n[bold cyan]📄 문서 전체 조회: {source_file}[/bold cyan]\n")

    results = get_full_document(source_file, limit)
    documents = results.get("data", {}).get("Get", {}).get("Documents", [])

    if not documents:
        print_output(f"[yellow]⚠️ '{source_file}' 문서를 찾을 수 없습니다.[/yellow]")
        return

    # original_index로 정렬 (None은 맨 뒤로)
    sorted_docs = sorted(
        documents, key=lambda x: (x.get("original_index") is None, x.get("original_index") or 0)
    )

    print_output(f"[green]✅ {len(sorted_docs)}개의 청크를 찾았습니다.[/green]\n")
    print("=" * 80)

    # 전체 내용 출력
    full_content = []
    for doc in sorted_docs:
        content = doc.get("content", "")
        full_content.append(content)

    print("\n".join(full_content))
    print("\n" + "=" * 80)


def expand_document(query: str, source_filter: str | None = None, limit: int = 100):
    """
    키워드가 포함된 문서의 전체 내용 조회

    키워드로 검색 후, 해당 청크에서 전화번호를 추출하여
    같은 전화번호를 가진 모든 청크를 가져옵니다.
    """
    import re as regex

    print_output(f"\n[bold cyan]🔍 '{query}' 포함 문서 전체 조회[/bold cyan]\n")

    # 1. 키워드로 검색
    results = text_search(query, 10, source_filter)
    documents = results.get("data", {}).get("Get", {}).get("Documents", [])

    if not documents:
        print_output(f"[yellow]⚠️ '{query}'를 포함한 문서를 찾을 수 없습니다.[/yellow]")
        return

    # 2. 첫 번째 결과에서 전화번호 추출
    first_doc = documents[0]
    content = first_doc.get("content", "")
    source_file = first_doc.get("source_file", "")

    # 전화번호 패턴 찾기
    phone_pattern = regex.compile(r"전화번호\s*[:\s]*([\d-]+)")
    phone_match = phone_pattern.search(content)

    if phone_match:
        phone_number = phone_match.group(1)
        print_output(f"[green]📞 전화번호 발견: {phone_number}[/green]")
        print_output(f"[green]📁 소스: {source_file}[/green]\n")

        # 3. 같은 전화번호를 가진 모든 청크 검색
        all_results = text_search(phone_number, limit, source_filter)
        all_docs = all_results.get("data", {}).get("Get", {}).get("Documents", [])

        if all_docs:
            print_output(f"[green]✅ {len(all_docs)}개의 관련 청크를 찾았습니다.[/green]\n")
            print("=" * 80)

            # 중복 제거 및 정렬
            seen_ids = set()
            unique_docs = []
            for doc in all_docs:
                doc_id = doc.get("_additional", {}).get("id", "")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_docs.append(doc)

            # 내용 출력
            for i, doc in enumerate(unique_docs, 1):
                doc_content = doc.get("content", "")
                print(f"\n[청크 {i}]\n{doc_content}")

            print("\n" + "=" * 80)
        else:
            print_output("[yellow]⚠️ 관련 청크를 찾을 수 없습니다.[/yellow]")
    else:
        # 전화번호가 없으면 키워드로 찾은 모든 결과 출력
        print_output(
            "[yellow]⚠️ 전화번호를 찾을 수 없습니다. 키워드 검색 결과를 표시합니다.[/yellow]\n"
        )
        print_output(f"[green]📁 소스: {source_file}[/green]")
        print_output(f"[green]✅ {len(documents)}개의 청크를 찾았습니다.[/green]\n")
        print("=" * 80)

        for i, doc in enumerate(documents, 1):
            doc_content = doc.get("content", "")
            print(f"\n[청크 {i}]\n{doc_content}")

        print("\n" + "=" * 80)


def get_collection_stats() -> dict:
    """
    컬렉션 통계 조회

    Returns:
        총 문서 개수 및 소스별 분포
    """
    # 총 개수
    count_query = """
    {
        Aggregate {
            Documents {
                meta {
                    count
                }
            }
        }
    }
    """

    # 소스별 분포
    group_query = """
    {
        Aggregate {
            Documents(groupBy: "source_file") {
                groupedBy {
                    value
                }
                meta {
                    count
                }
            }
        }
    }
    """

    count_result = execute_query(count_query)
    group_result = execute_query(group_query)

    return {
        "total_count": count_result["data"]["Aggregate"]["Documents"][0]["meta"]["count"],
        "by_source": group_result["data"]["Aggregate"]["Documents"],
    }


def highlight_text(text: str, query: str):
    """
    검색어를 하이라이팅하여 Rich Text 반환 (Rich 없으면 원본 반환)

    Args:
        text: 원본 텍스트
        query: 검색어

    Returns:
        하이라이팅된 Rich Text 또는 원본 텍스트
    """
    if not RICH_AVAILABLE:
        return text

    rich_text = Text()

    # 대소문자 무시 검색
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    last_end = 0
    for match in pattern.finditer(text):
        # 매치 전 텍스트
        rich_text.append(text[last_end : match.start()])
        # 매치된 텍스트 (하이라이팅)
        rich_text.append(match.group(), style="bold yellow on red")
        last_end = match.end()

    # 나머지 텍스트
    rich_text.append(text[last_end:])

    return rich_text


def display_results(results: dict, query: str, mode: str):
    """
    검색 결과를 포맷팅하여 출력

    Args:
        results: GraphQL 응답
        query: 검색어 (하이라이팅용)
        mode: 검색 모드 (text/semantic)
    """
    documents = results.get("data", {}).get("Get", {}).get("Documents", [])

    if not documents:
        print_output("[yellow]⚠️ 검색 결과가 없습니다.[/yellow]")
        return

    print_output(f"\n[green]✅ {len(documents)}개의 결과를 찾았습니다.[/green]\n")

    for i, doc in enumerate(documents, 1):
        content = doc.get("content", "")
        additional = doc.get("_additional", {})

        # 내용이 너무 길면 자르기
        if len(content) > 1000:
            content = content[:1000] + "..."

        if RICH_AVAILABLE:
            # Rich 출력
            meta_table = Table(show_header=False, box=None, padding=(0, 1))
            meta_table.add_column("Key", style="cyan")
            meta_table.add_column("Value", style="white")

            meta_table.add_row("📁 Source", doc.get("source_file", "N/A"))

            if doc.get("original_index") is not None:
                meta_table.add_row("📍 Index", str(doc.get("original_index")))

            if mode == "semantic" and additional:
                if "certainty" in additional:
                    meta_table.add_row("🎯 Certainty", f"{additional['certainty']:.2%}")
                if "distance" in additional:
                    meta_table.add_row("📏 Distance", f"{additional['distance']:.4f}")

            if additional.get("id"):
                meta_table.add_row("🔑 ID", additional["id"][:8] + "...")

            if mode == "text":
                highlighted_content = highlight_text(content, query)
            else:
                highlighted_content = Text(content)

            panel_content = Text()
            panel_content.append_text(highlighted_content)

            console.print(
                Panel(
                    panel_content,
                    title=f"[bold blue]결과 #{i}[/bold blue]",
                    subtitle=meta_table,
                    border_style="blue",
                )
            )
            console.print()
        else:
            # 기본 출력
            print(f"\n{'='*60}")
            print(f"결과 #{i}")
            print(f"{'='*60}")
            print(f"📁 Source: {doc.get('source_file', 'N/A')}")

            if doc.get("original_index") is not None:
                print(f"📍 Index: {doc.get('original_index')}")

            if mode == "semantic" and additional:
                if "certainty" in additional:
                    print(f"🎯 Certainty: {additional['certainty']:.2%}")
                if "distance" in additional:
                    print(f"📏 Distance: {additional['distance']:.4f}")

            if additional.get("id"):
                print(f"🔑 ID: {additional['id'][:8]}...")

            print(f"\n내용:\n{content}\n")


def display_stats():
    """컬렉션 통계 출력"""
    print_output("\n[bold cyan]📊 Weaviate 컬렉션 통계[/bold cyan]\n")

    stats = get_collection_stats()

    print_output(f"[green]총 문서 개수: {stats['total_count']:,}개[/green]\n")

    if RICH_AVAILABLE:
        # Rich 테이블
        table = Table(title="소스별 문서 분포")
        table.add_column("소스 파일", style="cyan")
        table.add_column("문서 개수", justify="right", style="green")

        for item in sorted(stats["by_source"], key=lambda x: x["meta"]["count"], reverse=True):
            source = item["groupedBy"]["value"]
            count = item["meta"]["count"]
            table.add_row(source, f"{count:,}")

        console.print(table)
    else:
        # 기본 출력
        print("\n소스별 문서 분포:")
        print("-" * 50)
        for item in sorted(stats["by_source"], key=lambda x: x["meta"]["count"], reverse=True):
            source = item["groupedBy"]["value"]
            count = item["meta"]["count"]
            print(f"  {source}: {count:,}개")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Weaviate DB 검색 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  %(prog)s --query "이용요금"                      # 텍스트 검색
  %(prog)s --query "서비스 가격" --mode semantic   # 시맨틱 검색
  %(prog)s --query "키워드" --source notion_domain_1
  %(prog)s --stats                                 # 통계 조회
        """,
    )

    parser.add_argument("--query", "-q", type=str, help="검색어")

    parser.add_argument(
        "--mode", "-m", choices=["text", "semantic"], default="text", help="검색 모드 (기본: text)"
    )

    parser.add_argument("--limit", "-l", type=int, default=5, help="최대 결과 개수 (기본: 5)")

    parser.add_argument("--source", "-s", type=str, help="source_file 필터")

    parser.add_argument("--stats", action="store_true", help="컬렉션 통계 조회")

    parser.add_argument(
        "--full-doc",
        "-f",
        type=str,
        metavar="SOURCE_FILE",
        help="특정 source_file의 전체 문서 조회 (예: notion_domain_1)",
    )

    parser.add_argument(
        "--expand",
        "-e",
        action="store_true",
        help="키워드가 포함된 문서의 전체 내용 조회 (전화번호 기반)",
    )

    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    args = parser.parse_args()

    # 통계 조회
    if args.stats:
        display_stats()
        return

    # 전체 문서 조회
    if args.full_doc:
        display_full_document(args.full_doc, args.limit)
        return

    # 검색어 필수 확인
    if not args.query:
        parser.error("검색어(--query)를 입력하세요. 또는 --stats, --full-doc 옵션을 사용하세요.")

    # 문서 전체 확장 조회
    if args.expand:
        expand_document(args.query, args.source, args.limit)
        return

    # 헤더 출력
    if RICH_AVAILABLE:
        console.print(
            Panel(
                f"[bold]검색어:[/bold] {args.query}\n"
                f"[bold]모드:[/bold] {args.mode}\n"
                f"[bold]소스:[/bold] {args.source or '전체'}",
                title="🔍 Weaviate 검색",
                border_style="green",
            )
        )
    else:
        print("\n🔍 Weaviate 검색")
        print(f"검색어: {args.query}")
        print(f"모드: {args.mode}")
        print(f"소스: {args.source or '전체'}\n")

    try:
        # 검색 실행
        if args.mode == "text":
            results = text_search(args.query, args.limit, args.source)
        else:
            results = semantic_search(args.query, args.limit, args.source)

        # 결과 출력
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            display_results(results, args.query, args.mode)

    except Exception as e:
        print_output(f"[red]❌ 오류 발생: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
