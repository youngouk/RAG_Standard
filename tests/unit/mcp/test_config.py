"""MCP 설정 로딩 테스트"""

from pathlib import Path


def test_mcp_yaml_exists():
    """mcp.yaml 파일 존재 확인"""
    yaml_path = Path("app/config/features/mcp.yaml")
    assert yaml_path.exists(), f"MCP 설정 파일이 없습니다: {yaml_path}"


def test_mcp_yaml_structure():
    """mcp.yaml 구조 확인"""
    import yaml

    with open("app/config/features/mcp.yaml") as f:
        config = yaml.safe_load(f)

    assert "mcp" in config, "mcp 키가 없습니다"
    assert "enabled" in config["mcp"], "enabled 키가 없습니다"
    assert "tools" in config["mcp"], "tools 키가 없습니다"


def test_mcp_tools_have_required_fields():
    """각 도구에 필수 필드가 있는지 확인"""
    import yaml

    with open("app/config/features/mcp.yaml") as f:
        config = yaml.safe_load(f)

    tools = config["mcp"]["tools"]
    required_fields = ["enabled", "description"]

    for tool_name, tool_config in tools.items():
        for field in required_fields:
            assert field in tool_config, f"{tool_name}에 {field} 필드가 없습니다"


def test_mcp_server_name_exists():
    """server_name 필드 존재 확인"""
    import yaml

    with open("app/config/features/mcp.yaml") as f:
        config = yaml.safe_load(f)

    assert "server_name" in config["mcp"], "server_name 키가 없습니다"
    # 범용화: 도메인 특화 이름에서 일반 이름으로 변경됨
    assert config["mcp"]["server_name"] == "blank-rag-system"


def test_mcp_has_vector_search_tools():
    """벡터 검색 관련 도구가 있는지 확인"""
    import yaml

    with open("app/config/features/mcp.yaml") as f:
        config = yaml.safe_load(f)

    tools = config["mcp"]["tools"]

    # 범용화: search_weaviate → search_vector_db로 이름 변경됨
    assert "search_vector_db" in tools, "search_vector_db 도구가 없습니다"
    assert tools["search_vector_db"]["enabled"] is True


