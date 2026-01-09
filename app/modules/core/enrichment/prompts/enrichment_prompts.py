"""
Enrichment 프롬프트 템플릿

LLM 문서 보강을 위한 프롬프트를 정의합니다.
"""

# 시스템 프롬프트 (공통)
SYSTEM_PROMPT = """당신은 고객 상담 데이터를 분석하여 메타데이터를 추출하는 AI 어시스턴트입니다.
주어진 대화 내용을 분석하여 다음 정보를 정확하게 추출해주세요:

1. category_main: 주요 카테고리 (예: "결제", "회원관리", "보너스기능", "상품문의" 등)
2. category_sub: 세부 카테고리 (예: "친구초대", "결제수단", "회원가입" 등)
3. intent: 사용자 의도 (예: "기능 설명 요청", "문제 해결 요청", "정보 확인 요청" 등)
4. consult_type: 상담 유형 (예: "초대코드문의", "결제오류", "가입문의" 등)
5. keywords: 핵심 키워드 리스트 (3-7개, 중요도 순)
6. summary: 대화 요약 (한 줄, 50자 이내)
7. is_tool_related: 도구/기능 관련 여부 (true/false)
8. requires_db_check: 데이터베이스 확인 필요 여부 (true/false)

응답은 반드시 JSON 형식으로만 작성하고, 다른 설명은 추가하지 마세요."""

# Few-shot 예시 (2개)
FEW_SHOT_EXAMPLES = """
예시 1:
입력:
고객: 친구 초대 코드는 어디서 입력하나요?
상담원: 회원가입 후 로그인→설정(톱니)→전화번호 인증→혜택 탭→친구초대→'친구에게 받은 초대코드 입력하기'에서 코드 입력하시면 됩니다.

출력:
{
  "category_main": "보너스기능",
  "category_sub": "친구초대",
  "intent": "기능 설명 요청",
  "consult_type": "초대코드문의",
  "keywords": ["친구초대", "초대코드", "입력방법", "혜택탭", "전화번호인증"],
  "summary": "친구 초대 코드 입력 위치 안내",
  "is_tool_related": false,
  "requires_db_check": false
}

예시 2:
입력:
고객: 결제가 안 돼요. 계속 오류가 나요.
상담원: 어떤 결제 수단을 사용하셨나요? 카드사에서 일시적으로 차단했을 수 있습니다. 다른 카드로 시도해보시거나 카드사에 문의해주세요.

출력:
{
  "category_main": "결제",
  "category_sub": "결제오류",
  "intent": "문제 해결 요청",
  "consult_type": "결제실패",
  "keywords": ["결제오류", "결제실패", "카드", "오류", "결제수단"],
  "summary": "결제 오류 발생, 카드사 확인 필요",
  "is_tool_related": false,
  "requires_db_check": true
}
"""

# 사용자 프롬프트 템플릿
USER_PROMPT_TEMPLATE = """다음 고객 상담 내용을 분석하여 JSON 형식으로 메타데이터를 추출해주세요:

{content}

위 내용을 분석하여 다음 JSON 형식으로 응답해주세요:
{{
  "category_main": "주요 카테고리",
  "category_sub": "세부 카테고리",
  "intent": "사용자 의도",
  "consult_type": "상담 유형",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "summary": "한 줄 요약",
  "is_tool_related": false,
  "requires_db_check": false
}}

주의: JSON만 출력하고 다른 설명은 추가하지 마세요."""


def build_enrichment_prompt(content: str, include_examples: bool = True) -> tuple[str, str]:
    """
    보강 프롬프트 생성

    Args:
        content: 분석할 문서 내용
        include_examples: Few-shot 예시 포함 여부 (기본: True)

    Returns:
        tuple[str, str]: (system_prompt, user_prompt)

    사용 예시:
        >>> system_prompt, user_prompt = build_enrichment_prompt(
        ...     "고객: 친구 초대 코드 입력 방법\n상담원: ..."
        ... )
        >>> # LLM에 전달
        >>> response = llm.chat([
        ...     {"role": "system", "content": system_prompt},
        ...     {"role": "user", "content": user_prompt}
        ... ])
    """
    # 시스템 프롬프트 구성
    system_prompt = SYSTEM_PROMPT
    if include_examples:
        system_prompt += "\n\n" + FEW_SHOT_EXAMPLES

    # 사용자 프롬프트 구성
    user_prompt = USER_PROMPT_TEMPLATE.format(content=content)

    return system_prompt, user_prompt


def build_batch_enrichment_prompt(
    documents: list[dict], include_examples: bool = True
) -> tuple[str, str]:
    """
    배치 보강 프롬프트 생성 (최대 10개 문서)

    Args:
        documents: 분석할 문서 리스트 (각 문서는 content 필드 포함)
        include_examples: Few-shot 예시 포함 여부 (기본: True)

    Returns:
        tuple[str, str]: (system_prompt, user_prompt)

    사용 예시:
        >>> documents = [
        ...     {"content": "친구 초대 코드..."},
        ...     {"content": "결제 오류..."}
        ... ]
        >>> system_prompt, user_prompt = build_batch_enrichment_prompt(documents)
    """
    # 시스템 프롬프트 (동일)
    system_prompt = SYSTEM_PROMPT
    if include_examples:
        system_prompt += "\n\n" + FEW_SHOT_EXAMPLES

    # 배치 사용자 프롬프트 구성
    batch_content = ""
    for i, doc in enumerate(documents[:10], 1):  # 최대 10개
        content = doc.get("content", "")
        batch_content += f"\n\n--- 문서 {i} ---\n{content}"

    user_prompt = f"""다음 {len(documents[:10])}개의 고객 상담 내용을 각각 분석하여 JSON 배열로 응답해주세요:
{batch_content}

각 문서에 대해 다음 JSON 형식으로 응답해주세요 (배열 형태):
[
  {{
    "category_main": "주요 카테고리",
    "category_sub": "세부 카테고리",
    "intent": "사용자 의도",
    "consult_type": "상담 유형",
    "keywords": ["키워드1", "키워드2"],
    "summary": "한 줄 요약",
    "is_tool_related": false,
    "requires_db_check": false
  }},
  ...
]

주의: JSON 배열만 출력하고 다른 설명은 추가하지 마세요."""

    return system_prompt, user_prompt
