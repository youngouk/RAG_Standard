"""
SQL Generation 프롬프트 모듈

LLM이 SQL 쿼리를 생성하기 위한 프롬프트 템플릿을 제공합니다.
"""

from .sql_generation import (
    SQL_GENERATION_SYSTEM_PROMPT,
    SQL_TEMPLATES,
    get_sql_generation_prompt,
)

__all__ = [
    "SQL_GENERATION_SYSTEM_PROMPT",
    "SQL_TEMPLATES",
    "get_sql_generation_prompt",
]
