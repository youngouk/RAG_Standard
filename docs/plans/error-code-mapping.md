# 에러코드 매핑 테이블

## 목차
- [AUTH (인증/인가)](#auth-인증인가)
- [SESSION (세션 관리)](#session-세션-관리)
- [SERVICE (서비스 초기화)](#service-서비스-초기화)
- [DOC (문서 처리)](#doc-문서-처리)
- [UPLOAD (파일 업로드)](#upload-파일-업로드)
- [IMAGE (이미지 처리)](#image-이미지-처리)
- [LLM (언어 모델)](#llm-언어-모델)
- [VECTOR (벡터 검색)](#vector-벡터-검색)
- [DB (데이터베이스)](#db-데이터베이스)

---

## AUTH (인증/인가)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| AUTH-001 | app/lib/auth.py | 93 | RuntimeError | FASTAPI_AUTH_KEY 환경 변수가 설정되지 않았습니다 | 프로덕션 환경에서 API Key 미설정 |
| AUTH-002 | app/lib/auth.py | 204 | HTTPException(500) | 서버 인증 설정 오류 | 프로덕션 환경에서 API 인증 미구성 |
| AUTH-003 | app/lib/auth.py | 248 | JSONResponse(401) | API Key가 필요합니다 | X-API-Key 헤더 누락 |
| AUTH-004 | app/lib/auth.py | 278 | JSONResponse(401) | 제공된 API Key가 유효하지 않습니다 | API Key 검증 실패 |
| AUTH-005 | app/lib/auth.py | 401 | HTTPException(401) | API Key가 필요합니다 | get_api_key() 함수에서 헤더 누락 |
| AUTH-006 | app/lib/auth.py | 421 | HTTPException(401) | 제공된 API Key가 유효하지 않습니다 | get_api_key() 함수에서 검증 실패 |

---

## SESSION (세션 관리)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| SESSION-001 | app/api/routers/chat_router.py | 152 | HTTPException(400) | 세션 처리 실패 | 세션 요청 처리 실패 |
| SESSION-002 | app/api/routers/chat_router.py | 335 | HTTPException(500) | 세션 모듈 오류 | 세션 모듈 초기화 실패 (create_session) |
| SESSION-003 | app/api/routers/chat_router.py | 380 | HTTPException(500) | 세션 생성 실패 | 새 세션 생성 중 예외 발생 |
| SESSION-004 | app/api/routers/chat_router.py | 406 | HTTPException(500) | 세션 모듈 오류 | 세션 모듈 초기화 실패 (get_chat_history) |
| SESSION-005 | app/api/routers/chat_router.py | 434 | HTTPException(404) | 세션을 찾을 수 없습니다 | 히스토리 조회 시 세션 없음 |
| SESSION-006 | app/api/routers/chat_router.py | 444 | HTTPException(500) | 히스토리 조회 실패 | 채팅 히스토리 조회 중 예외 |
| SESSION-007 | app/api/routers/chat_router.py | 469 | HTTPException(500) | 세션 모듈 오류 | 세션 모듈 초기화 실패 (delete_session) |
| SESSION-008 | app/api/routers/chat_router.py | 491 | HTTPException(404) | 세션을 찾을 수 없습니다 | 삭제할 세션 없음 |
| SESSION-009 | app/api/routers/chat_router.py | 501 | HTTPException(500) | 세션 삭제 실패 | 세션 삭제 중 예외 |
| SESSION-010 | app/api/routers/chat_router.py | 533 | HTTPException(500) | 통계 조회 실패 | 시스템 통계 조회 중 예외 |
| SESSION-011 | app/api/routers/chat_router.py | 569 | HTTPException(404) | 세션을 찾을 수 없습니다 | 세션 정보 조회 시 세션 없음 |
| SESSION-012 | app/api/routers/chat_router.py | 580 | HTTPException(500) | 세션 정보 조회 실패 | 세션 정보 조회 중 예외 |

---

## SERVICE (서비스 초기화)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| SERVICE-001 | app/api/routers/chat_router.py | 101 | HTTPException(503) | 서비스 초기화 중 | ChatService 초기화되지 않음 |
| SERVICE-002 | app/api/routers/chat_router.py | 127 | ValueError | Invalid quality score | quality score가 0.0-1.0 범위 벗어남 |

---

## DOC (문서 처리)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| DOC-001 | app/api/documents.py | 60 | HTTPException(500) | 검색 모듈 초기화 실패 | retrieval_module 없음 (get_document_stats) |
| DOC-002 | app/api/documents.py | 83 | HTTPException(500) | 문서 통계 조회 실패 | 문서 통계 조회 중 예외 |
| DOC-003 | app/api/documents.py | 115 | HTTPException(400) | 확인 코드 불일치 | 문서 삭제 확인 코드 오류 |
| DOC-004 | app/api/documents.py | 127 | HTTPException(500) | 검색 모듈 초기화 실패 | retrieval_module 없음 (delete_all_documents) |
| DOC-005 | app/api/documents.py | 183 | HTTPException(500) | 부분 삭제 완료 | 일부 문서만 삭제됨 |
| DOC-006 | app/api/documents.py | 198 | HTTPException(500) | 삭제 상태 확인 실패 | 문서 삭제 후 상태 확인 실패 |
| DOC-007 | app/api/documents.py | 244 | HTTPException(500) | 문서 삭제 실패 | 문서 삭제 중 예외 |
| DOC-008 | app/api/documents.py | 268 | HTTPException(403) | 권한 없음 | 컬렉션 초기화 디버그 모드 아님 |
| DOC-009 | app/api/documents.py | 281 | HTTPException(500) | 검색 모듈 초기화 실패 | retrieval_module 없음 (clear_collection_safe) |
| DOC-010 | app/api/documents.py | 302 | HTTPException(500) | 컬렉션 초기화 실패 | 컬렉션 초기화 중 예외 |
| DOC-011 | app/api/documents.py | 324 | HTTPException(500) | 검색 모듈 초기화 실패 | retrieval_module 없음 (backup_metadata) |
| DOC-012 | app/api/documents.py | 346 | HTTPException(500) | 메타데이터 백업 실패 | 메타데이터 백업 중 예외 |
| DOC-013 | app/modules/core/documents/document_processing.py | 123 | FileNotFoundError | File not found | 파일 경로가 존재하지 않음 |
| DOC-014 | app/modules/core/documents/document_processing.py | 128 | ValueError | 지원하지 않는 파일 형식입니다 | 파일 타입 미지원 |
| DOC-015 | app/modules/core/documents/document_processing.py | 156 | RuntimeError | 파일을 읽을 수 없습니다 | 문서 로드 중 예외 |
| DOC-016 | app/modules/core/documents/document_processing.py | 420 | RuntimeError | 문서 청킹 중 오류가 발생했습니다 | 문서 분할 중 예외 |

---

## UPLOAD (파일 업로드)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| UPLOAD-001 | app/api/upload.py | 192 | ValidationError | 지원하지 않는 파일 형식 | content_type 미지원 |
| UPLOAD-002 | app/api/upload.py | 210 | ValidationError | 파일 크기 초과 | 파일 크기가 max_size 초과 |
| UPLOAD-003 | app/api/upload.py | 232 | Exception | Required modules not available | document_processor 또는 retrieval_module 없음 |
| UPLOAD-004 | app/api/upload.py | 316 | HTTPException(400) | Validation error | 파일 검증 실패 |
| UPLOAD-005 | app/api/upload.py | 323 | HTTPException(400) | 잘못된 파일명 | 파일명 유효하지 않음 |
| UPLOAD-006 | app/api/upload.py | 338 | HTTPException(400) | 보안 검증 실패 | Path Traversal 시도 차단 |
| UPLOAD-007 | app/api/upload.py | 351 | HTTPException(400) | 파일 경로 검증 실패 | 파일 경로 검증 중 오류 |
| UPLOAD-008 | app/api/upload.py | 409 | HTTPException(500) | 업로드 실패 | 파일 업로드 중 예외 |
| UPLOAD-009 | app/api/upload.py | 431 | HTTPException(404) | 작업을 찾을 수 없음 | job_id가 존재하지 않음 |
| UPLOAD-010 | app/api/upload.py | 465 | HTTPException(500) | 시스템 모듈 사용 불가 | retrieval_module 없음 (list_documents) |
| UPLOAD-011 | app/api/upload.py | 510 | HTTPException(500) | 문서 목록 조회 실패 | 문서 목록 조회 중 예외 |
| UPLOAD-012 | app/api/upload.py | 530 | HTTPException(500) | 시스템 모듈 사용 불가 | retrieval_module 없음 (delete_document) |
| UPLOAD-013 | app/api/upload.py | 551 | HTTPException(500) | 문서 삭제 실패 | 문서 삭제 중 예외 |
| UPLOAD-014 | app/api/upload.py | 570 | HTTPException(500) | 시스템 모듈 사용 불가 | retrieval_module 없음 (bulk_delete) |
| UPLOAD-015 | app/api/upload.py | 611 | HTTPException(500) | 일괄 삭제 실패 | 일괄 삭제 중 예외 |

---

## IMAGE (이미지 처리)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| IMAGE-001 | app/api/image_chat.py | 129 | HTTPException(400) | 이미지 개수 제한 초과 | 이미지 개수 > 3600 |
| IMAGE-002 | app/api/image_chat.py | 148 | HTTPException(400) | 이미지 검증 실패 | 파일 형식 또는 크기 검증 실패 |
| IMAGE-003 | app/api/image_chat.py | 166 | HTTPException(400) | 이미지 내용 검증 실패 | PIL 이미지 검증 실패 |
| IMAGE-004 | app/api/image_chat.py | 206 | HTTPException(503) | 이미지 분석 서비스 사용 불가 | generate_multimodal 메서드 없음 |
| IMAGE-005 | app/api/image_chat.py | 245 | HTTPException(500) | 이미지 처리 오류 | 이미지 처리 중 예외 |

---

## LLM (언어 모델)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| LLM-001 | app/modules/core/generation/generator.py | 161 | ValueError | OpenRouter API 키가 설정되지 않았습니다 | OPENROUTER_API_KEY 환경 변수 미설정 |
| LLM-002 | app/modules/core/generation/generator.py | 292 | RuntimeError | 답변 생성 실패 | 모든 fallback 모델 실패 |
| LLM-003 | app/modules/core/generation/generator.py | 316 | RuntimeError | OpenRouter 클라이언트가 초기화되지 않았습니다 | 클라이언트 미초기화 상태에서 생성 시도 |
| LLM-004 | app/modules/core/generation/generator.py | 327 | ValueError | 검색된 문서가 없습니다 | context_text가 비어있음 |
| LLM-005 | app/modules/core/generation/generator.py | 505 | ValueError | 프롬프트 템플릿을 찾을 수 없습니다 | 프롬프트 템플릿 파일 없음 (예외 catch) |
| LLM-006 | app/modules/core/generation/generator.py | 512 | ValueError | 프롬프트 템플릿을 찾을 수 없습니다 | 프롬프트 템플릿 None 반환 |
| LLM-007 | app/modules/core/generation/generator.py | 417 | GenerationError(GENERATION_TIMEOUT) | AI 응답 시간이 초과되었습니다 | OpenRouter API 타임아웃 |

---

## VECTOR (벡터 검색)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| VECTOR-001 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 177 | ConnectionError | Weaviate 벡터 데이터베이스에 연결할 수 없습니다 | Weaviate 연결 실패 |
| VECTOR-002 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 189 | RuntimeError | Weaviate 'Documents' 컬렉션이 존재하지 않습니다 | Documents 컬렉션 없음 (initialize) |
| VECTOR-003 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 296 | RuntimeError | Weaviate 'Documents' 컬렉션이 존재하지 않습니다 | Documents 컬렉션 없음 (search) |
| VECTOR-004 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 313 | ValueError | Embedding은 list 타입이어야 합니다 | query_embedding 타입 오류 |
| VECTOR-005 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 348 | RuntimeError | Weaviate 검색 중 오류가 발생했습니다 | WeaviateQueryError 발생 |
| VECTOR-006 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 598 | RuntimeError | Weaviate 'Documents' 컬렉션이 존재하지 않습니다 | Documents 컬렉션 없음 (add_documents) |
| VECTOR-007 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 615 | ValueError | 문서에 'content' 필드가 없습니다 | 문서 content 필드 누락 |
| VECTOR-008 | app/modules/core/retrieval/retrievers/weaviate_retriever.py | 617 | ValueError | 문서에 'embedding' 필드가 없습니다 | 문서 embedding 필드 누락 |
| VECTOR-009 | app/infrastructure/storage/vector/weaviate_store.py | 28 | ValueError | WEAVIATE_URL 환경 변수가 필요합니다 | WEAVIATE_URL 미설정 |
| VECTOR-010 | app/infrastructure/storage/vector/weaviate_store.py | 72 | RuntimeError | 문서 인덱싱 중 오류가 발생했습니다 | 배치 업로드 중 실패한 문서 존재 |
| VECTOR-011 | app/infrastructure/storage/vector/weaviate_store.py | 84 | RuntimeError | 문서 인덱싱 중 오류가 발생했습니다 | add_documents 중 예외 |
| VECTOR-012 | app/infrastructure/storage/vector/weaviate_store.py | 135 | RuntimeError | 문서 삭제 실패 | delete 중 예외 |

---

## DB (데이터베이스)

| 코드 | 파일 | 라인 | 에러 타입 | 한국어 메시지 | 발생 조건 |
|------|------|------|---------|------------|---------|
| DB-001 | app/infrastructure/persistence/connection.py | 93 | ConnectionError | PostgreSQL 데이터베이스에 연결할 수 없습니다: DATABASE_URL이 설정되지 않았습니다 | DATABASE_URL 미설정 |
| DB-002 | app/infrastructure/persistence/connection.py | 141 | ConnectionError | PostgreSQL 데이터베이스에 연결할 수 없습니다 | 연결 테스트 실패 |
| DB-003 | app/infrastructure/persistence/connection.py | 158 | RuntimeError | 데이터베이스 마이그레이션 실패 | 초기화 중 예외 (마이그레이션 관련) |
| DB-004 | app/infrastructure/persistence/connection.py | 169 | RuntimeError | 데이터베이스가 초기화되지 않았습니다 | engine 없이 create_tables 호출 |
| DB-005 | app/infrastructure/persistence/connection.py | 178 | RuntimeError | 데이터베이스가 초기화되지 않았습니다 | engine 없이 drop_tables 호출 |
| DB-006 | app/infrastructure/persistence/connection.py | 202 | RuntimeError | 데이터베이스가 초기화되지 않았습니다 | async_session_maker 없이 get_session 호출 |

---

## 통계 요약

- **AUTH**: 6개 에러 코드
- **SESSION**: 12개 에러 코드
- **SERVICE**: 2개 에러 코드
- **DOC**: 16개 에러 코드
- **UPLOAD**: 15개 에러 코드
- **IMAGE**: 5개 에러 코드
- **LLM**: 7개 에러 코드
- **VECTOR**: 12개 에러 코드
- **DB**: 6개 에러 코드

**총 에러 코드**: 81개
