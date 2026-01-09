# RAG Chatbot Project Context (v3.3.0 - Perfect State)

## Interaction Guidelines
- **Language**: **모든 답변은 무조건 한국어로 작성합니다.** (All responses must be in Korean).
- **Tone**: 전문가적이고 간결하며, 실행 가능한 코드와 명령어를 중심으로 답변합니다.

## Project Overview
도메인 범용화된 **완벽한 오픈소스 RAG 표준 시스템**.
고성능 **FastAPI** 기반으로 아키텍처와 기능성, 보안성을 모두 갖춘 Enterprise-ready 솔루션입니다.
v3.3.0에서 기술 부채를 전면 해결하고 지능형 GraphRAG와 통합 보안을 완성했습니다.

## Key Technologies
- **Backend**: Python 3.11+, FastAPI (Async).
- **LLM**: Multi-LLM support (Google Gemini 2.5 Pro [Primary], GPT-4o, Claude 3.5).
- **Vector DB**: **Weaviate** (Primary, Hybrid Search).
- **Advanced RAG**:
    - **GraphRAG v3.3**: 지식 그래프(NetworkX)에 **벡터 유사도 검색** 통합.
    - **Reranking**: Jina ColBERT v2 (토큰 레벨 정밀 리랭킹).
    - **Caching**: Semantic Cache (의미 기반 유사도 캐싱).
    - **Self-RAG**: 생성 답변 품질 자가 진단 및 재시도 로직.
- **Security**: 
    - **Unified PII Processor**: 통합 개인정보 마스킹 및 AI 리뷰 시스템.
    - **Admin Auth**: 모든 관리자 API에 대한 전역 API Key 인증 강제화.
- **Observability**: LangSmith & Langfuse (테스트 시 자동 격리 지원).

## Architecture & Directory Structure
- **`app/api/`**: REST API 및 서비스 레이어. 모든 관리자 API는 인증 필수.
- **`app/core/`**: DI Container (`AppContainer`) 및 아키텍처 규격.
- **`app/modules/core/`**: 시스템 브레인.
    - `graph/`: 벡터 검색이 통합된 지능형 GraphRAG.
    - `privacy/`: 통합 PII Facade 및 정책 기반 리뷰.
    - `retrieval/`: 하이브리드 검색, 리랭킹 체인, 시맨틱 캐시.
    - `routing/`: YAML 동적 키워드 기반 쿼리 라우터.
- **`app/infrastructure/`**: Storage 및 DB 어댑터.

## Project Status (Current)
- **Status**: ✅ **완전체 (The Perfect State)**
- **Tests**: **1,082개** 모든 테스트 통과.
- **Technical Debt**: **Zero (TODO 0건)**.
- **Quality**: `Ruff` & `Mypy` 엄격 모드 준수.

## Development Commands
- **Install**: `uv sync` (의존성 및 spaCy 모델 자동 설치)
- **Test**: `make test` (격리된 환경에서 1082개 테스트 실행)
- **Lint/Format**: `make lint`, `make format`
- **Run**: `make dev-reload` (8000 포트)