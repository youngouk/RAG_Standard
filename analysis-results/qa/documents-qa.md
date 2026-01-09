# Documents Module QA 분석 보고서

**분석 일시**: 2026-01-08
**분석 대상**: RAG_Standard v3.3.0 Documents Module
**분석자**: Document Processing QA Specialist

---

## 📋 Executive Summary

RAG_Standard의 Documents Module은 전반적으로 **잘 설계된 아키텍처**를 가지고 있으며, Strategy 패턴과 Factory 패턴을 적절히 활용하여 확장 가능한 구조를 갖추고 있습니다. 하지만 **몇 가지 중요한 이슈**가 발견되었으며, 특히 **인코딩 처리**와 **대용량 파일 처리** 영역에서 개선이 필요합니다.

### 주요 발견사항
- ✅ **우수**: Strategy/Factory 패턴 적용, 명확한 인터페이스 설계
- ⚠️ **주의**: UTF-8 인코딩 처리 불완전 (TextLoader만 cp949 폴백 지원)
- ⚠️ **주의**: 메모리 관리 미흡 (스트리밍 처리 미구현)
- ⚠️ **주의**: 오류 메시지 불명확 (디버깅 어려움)
- ❌ **심각**: PointRuleProcessor가 Factory에 미등록

---

## 1. 파일 형식별 로더 동작 분석

### 1.1 지원 파일 형식 매트릭스

| 형식 | 로더 클래스 | 상태 | UTF-8 폴백 | 대용량 처리 | 메타데이터 |
|------|-------------|------|------------|-------------|-----------|
| **PDF** | PDFLoader | ✅ 정상 | ❌ 없음 | ❌ 전체 로드 | page_number |
| **DOCX** | DOCXLoader | ✅ 정상 | ❌ 없음 | ❌ 전체 로드 | (없음) |
| **XLSX** | XLSXLoader | ✅ 정상 | ❌ 없음 | ❌ 전체 로드 | sheet |
| **CSV** | CSVLoader | ✅ 정상 | ❌ 없음 | ❌ 전체 로드 | (없음) |
| **JSON** | JSONLoader | ✅ 정상 | ✅ UTF-8 | ❌ 전체 로드 | (없음) |
| **Markdown** | MarkdownLoader | ✅ 정상 | ✅ UTF-8 | ❌ 전체 로드 | (없음) |
| **HTML** | HTMLLoader | ✅ 정상 | ✅ UTF-8 | ❌ 전체 로드 | (없음) |
| **TXT** | TextLoader | ✅ 정상 | ✅ cp949 | ❌ 전체 로드 | (없음) |

### 1.2 로더별 상세 분석

#### 1.2.1 PDFLoader
**파일 위치**: `app/modules/core/documents/loaders/pdf_loader.py`

**동작 방식**:
```python
with open(file_path, "rb") as file:
    reader = PdfReader(file)
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
```

**발견된 이슈**:
1. **인코딩 미지정**: 바이너리 모드(`"rb"`)로 열지만 `pypdf`가 내부적으로 인코딩 추론
2. **한 페이지 실패 시 계속 진행**: `try-except`로 개별 페이지 오류 처리 → 일부 페이지 누락 가능성
3. **메모리 효율성**: 모든 페이지를 메모리에 로드 (대용량 PDF 시 OOM 위험)

**권장사항**:
```python
# ❌ 현재 코드
documents.append(Document(page_content=text, metadata={"page_number": page_num + 1}))

# ✅ 개선안
if not text.strip():
    logger.warning(f"Empty page {page_num + 1} in {file_path.name}")
    continue  # 빈 페이지는 건너뛰기

documents.append(Document(
    page_content=text,
    metadata={
        "page_number": page_num + 1,
        "total_pages": len(reader.pages),  # 전체 페이지 수 추가
        "extraction_success": True
    }
))
```

#### 1.2.2 DOCXLoader
**파일 위치**: `app/modules/core/documents/loaders/docx_loader.py`

**발견된 이슈**:
1. **단락만 추출**: 표(table), 이미지 설명, 헤더/푸터 무시
2. **인코딩 처리 없음**: `python-docx`가 내부적으로 처리하지만 명시적 검증 없음
3. **빈 문서 처리**: 빈 문서 시 `[]` 반환하지만 경고만 로그

**권장사항**:
```python
# ✅ 개선안: 표와 이미지 설명도 추출
paragraphs = []
for paragraph in doc.paragraphs:
    if paragraph.text.strip():
        paragraphs.append(paragraph.text)

for table in doc.tables:
    for row in table.rows:
        row_text = ' | '.join(cell.text for cell in row.cells)
        if row_text.strip():
            paragraphs.append(row_text)
```

#### 1.2.3 XLSXLoader
**파일 위치**: `app/modules/core/documents/loaders/xlsx_loader.py`

**발견된 이슈**:
1. **시트별 단일 Document 생성**: 각 시트가 하나의 거대한 Document → 청킹 시 비효율
2. **인덱스 변수 미사용**: `_idx` 사용 (린터 경고 회피용이지만 실제로는 사용 안 함)
3. **메모리 비효율**: `pd.read_excel()` 전체 로드 → 수천 행 시 OOM 위험

**권장사항**:
```python
# ✅ 개선안: 청크 단위로 읽기
for chunk in pd.read_excel(file_path, sheet_name=sheet_name, chunksize=1000):
    # 1000행씩 처리
    for idx, row in chunk.iterrows():
        # ...
```

#### 1.2.4 CSVLoader
**파일 위치**: `app/modules/core/documents/loaders/csv_loader.py`

**발견된 이슈**:
1. **인코딩 추론 없음**: `pd.read_csv()` 기본 UTF-8 → 한글 CSV 실패 가능성
2. **전체 로드**: 대용량 CSV (수십만 행) 처리 불가

**권장사항**:
```python
# ✅ 개선안: 인코딩 자동 감지
try:
    df = pd.read_csv(file_path, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(file_path, encoding='cp949')  # 한글 Windows 인코딩
except:
    df = pd.read_csv(file_path, encoding='euc-kr')  # 한글 Unix 인코딩
```

#### 1.2.5 TextLoader ⭐
**파일 위치**: `app/modules/core/documents/loaders/text_loader.py`

**우수 사례**:
```python
try:
    with open(file_path, encoding="utf-8") as file:
        content = file.read()
except UnicodeDecodeError:
    # UTF-8 실패 시 cp949 폴백
    with open(file_path, encoding="cp949") as file:
        content = file.read()
```

**장점**:
- 다중 인코딩 폴백 전략 구현 ✅
- 명확한 오류 처리 ✅

**개선 필요**:
- 다른 로더들도 동일한 전략 적용 필요

---

## 2. 청킹 전략 검증

### 2.1 청킹 전략 비교

| 전략 | 클래스 | 용도 | 분할 방식 | 장점 | 단점 |
|------|--------|------|----------|------|------|
| **Simple** | SimpleChunker | FAQ | 1 항목 = 1 청크 | 구조 보존 | 크기 불균등 |
| **Point Rule** | PointRuleChunker | 포인트 규정 | 1 항목 = 1 청크 + HTML 파싱 | 도메인 특화 | 범용성 없음 |
| **Semantic** | SemanticChunker (외부) | 일반 문서 | 의미 경계 기반 | 의미 단위 | 비용↑, 속도↓ |
| **Recursive** | RecursiveCharacterTextSplitter (외부) | 일반 문서 | 고정 크기 + 구분자 | 빠름 | 의미 단절 |

### 2.2 SimpleChunker 분석
**파일 위치**: `app/modules/core/documents/chunking/simple_chunker.py`

**우수 사항**:
- 유연한 필드명 지원 (다국어 컬럼명 자동 인식)
  ```python
  question_keys = ["질문", "question", "Question", "Q", "query"]
  answer_keys = ["답변", "answer", "Answer", "A", "response"]
  ```
- 섹션/카테고리 자동 메타데이터 추출
- 템플릿 기반 콘텐츠 포맷팅

**발견된 이슈**:
1. **대용량 FAQ 처리**: 1만 개 FAQ 시 메모리 증가 (각 항목이 독립 청크)
2. **검증 로직 불완전**: 첫 번째 항목만 검증 → 나머지 항목 오류 가능성

### 2.3 PointRuleChunker 분석
**파일 위치**: `app/modules/core/documents/chunking/point_rule_chunker.py`

**우수 사항**:
- HTML 파싱 기능 (HTMLTextExtractor 커스텀 파서)
- 숫자 추출 정규식 (`_extract_number` 메서드)
- Markdown 형식 출력

**발견된 이슈**:
1. **HTML 파싱 오류 시 폴백**: `re.sub(r"<[^>]+>", "", html_content)` → 태그 제거만
2. **유효성 검사 미흡**: `항목명`만 필수 → 다른 필드 누락 시 부분 정보만 저장

**권장사항**:
```python
# ✅ 개선안: 필수 필드 강화
required_fields = ["항목명", "포인트적립액"]  # 포인트 금액도 필수화
```

---

## 3. 메타데이터 추출 정확도

### 3.1 RuleBasedExtractor 분석
**파일 위치**: `app/modules/core/documents/metadata/rule_based.py`

**추출 항목**:
1. **구조적 정보**: `contains_price`, `has_date`, `has_phone`, `has_email`
2. **텍스트 분석**: `keywords` (KoNLPy Okt 형태소 분석)
3. **도메인 분류**: `categories` (키워드 매칭)
4. **콘텐츠 유형**: `content_type` (question, instruction, info, conversation)

**우수 사항**:
- 정규식 패턴 클래스 변수로 컴파일 (성능 최적화)
  ```python
  PRICE_PATTERN = re.compile(r"\d{1,3}(,\d{3})*원|\d+만원|₩\d+")
  ```
- KoNLPy 옵션 처리 (설치 안 된 경우 폴백)

**발견된 이슈**:
1. **한국어 전용 패턴**: 영문 문서 처리 시 `categories` 빈 배열
2. **가격 패턴 한계**: "5000원", "50만원" 인식하지만 "$50", "€100" 미지원
3. **키워드 중복 제거 순서 의존**: `seen` 집합 사용하지만 순서 유지 로직 비효율

**권장사항**:
```python
# ✅ 개선안: 집합 사용으로 O(1) 검색
unique_keywords = list(dict.fromkeys(keywords))  # 순서 유지 + 중복 제거
```

---

## 4. 인코딩 처리 (한국어, UTF-8)

### 4.1 현재 상태 요약

| 로더 | UTF-8 지원 | cp949 폴백 | euc-kr 폴백 | 자동 감지 | 평가 |
|------|-----------|-----------|------------|----------|------|
| TextLoader | ✅ | ✅ | ❌ | ❌ | 🟢 양호 |
| JSONLoader | ✅ | ❌ | ❌ | ❌ | 🟡 기본 |
| MarkdownLoader | ✅ | ❌ | ❌ | ❌ | 🟡 기본 |
| HTMLLoader | ✅ | ❌ | ❌ | ❌ | 🟡 기본 |
| DOCXLoader | 내부 처리 | - | - | - | 🟡 기본 |
| PDFLoader | 내부 처리 | - | - | - | 🟡 기본 |
| CSVLoader | ❌ | ❌ | ❌ | ❌ | 🔴 위험 |
| XLSXLoader | ❌ | ❌ | ❌ | ❌ | 🔴 위험 |

### 4.2 심각도별 이슈

#### 🔴 High Priority (즉시 수정 필요)
**CSVLoader**: 한글 CSV 파일 읽기 실패 가능성 높음
```python
# 현재 코드 (위험)
df = pd.read_csv(file_path)  # 기본 UTF-8만 시도

# 실제 발생 가능 오류
# UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc0 in position 0
```

**해결 방안**:
```python
# ✅ 개선안
encodings = ['utf-8', 'cp949', 'euc-kr']
for encoding in encodings:
    try:
        df = pd.read_csv(file_path, encoding=encoding)
        logger.info(f"CSV loaded with {encoding} encoding")
        break
    except UnicodeDecodeError:
        continue
else:
    raise ValueError(f"Failed to decode CSV with any encoding: {encodings}")
```

#### 🟡 Medium Priority (개선 권장)
**HTMLLoader, MarkdownLoader**: Windows 환경에서 cp949 인코딩 파일 처리 불가

---

## 5. 대용량 파일 처리

### 5.1 메모리 사용량 분석

**테스트 시나리오 예측**:
- **PDF**: 500페이지 PDF → 약 200MB 메모리 (페이지당 400KB 추정)
- **XLSX**: 10,000행 엑셀 → 약 150MB 메모리
- **CSV**: 100,000행 CSV → 약 80MB 메모리

**현재 구현의 문제점**:
```python
# ❌ 모든 로더가 이 패턴 사용
documents = []
for item in data:
    documents.append(...)  # 전체 메모리에 적재
return documents  # 한 번에 반환
```

### 5.2 스트리밍 처리 미구현

**권장 구현**:
```python
# ✅ Generator 패턴 사용
async def load(self, file_path: Path) -> AsyncIterator[Document]:
    """스트리밍 방식으로 문서 로드"""
    reader = PdfReader(file_path)
    for page_num, page in enumerate(reader.pages):
        yield Document(...)  # 한 번에 하나씩 반환
```

**효과**:
- 메모리 사용량: O(N) → O(1)
- 첫 문서 처리 시작 시간: 즉시 (전체 로드 대기 불필요)

### 5.3 청킹 시 메모리 폭발

**document_processing.py** 분석:
```python
async def split_documents(self, documents: list[Document]) -> list[Document]:
    # ❌ 문제: 모든 문서를 메모리에 로드한 상태에서 청킹
    split_docs = await asyncio.to_thread(splitter.split_documents, documents)
    # 결과: documents (원본) + split_docs (청크) = 2배 메모리
```

**해결 방안**:
```python
# ✅ 개선안: 청킹 직후 원본 해제
for i, doc in enumerate(documents):
    chunks = splitter.split_text(doc.page_content)
    for chunk in chunks:
        yield Document(page_content=chunk, metadata=doc.metadata)
    # doc는 이 시점에서 가비지 컬렉션 대상
```

---

## 6. 파싱 실패 케이스

### 6.1 발견된 실패 시나리오

#### 케이스 1: PDF 텍스트 추출 실패
**파일**: `pdf_loader.py:32`
```python
try:
    text = page.extract_text()
except Exception as e:
    logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
    # ❌ 문제: 계속 진행하지만 해당 페이지 누락
```

**영향**:
- 이미지만 포함된 페이지 → 빈 문자열 또는 추출 실패
- OCR 없음 → 스캔 PDF 처리 불가

**개선안**:
- OCR 라이브러리 통합 (Tesseract, PaddleOCR)
- 실패 페이지 목록 메타데이터에 기록

#### 케이스 2: DOCX 구조 복잡도
**파일**: `docx_loader.py:28`
```python
paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
# ❌ 문제: 표, 이미지 설명, 텍스트 박스 무시
```

**실패 예시**:
- 업무 보고서 (표 중심) → 표 내용 누락
- 기술 문서 (이미지 설명 포함) → 설명 누락

#### 케이스 3: HTML 파싱 불완전
**파일**: `point_rule_chunker.py:306`
```python
except Exception as e:
    logger.warning(f"HTML parsing failed: {e}")
    return re.sub(r"<[^>]+>", "", html_content).strip()
    # ❌ 문제: 모든 태그 제거 → 구조 정보 손실
```

**실패 예시**:
```html
<h4>규정</h4>
<ul>
  <li>항목 1</li>
  <li>항목 2</li>
</ul>
```
→ 파싱 실패 시: "규정 항목 1 항목 2" (불릿 포인트 손실)

### 6.2 오류 메시지 품질

**현재 상태**:
```python
raise ValueError(f"Failed to load PDF file: {e}") from e
# ❌ 문제: 추상적인 메시지, 디버깅 어려움
```

**개선안**:
```python
# ✅ 구체적인 오류 메시지
raise ValueError(
    f"Failed to load PDF file: {file_path.name}\n"
    f"Error type: {type(e).__name__}\n"
    f"Error details: {str(e)}\n"
    f"Suggested action: Check if file is corrupted or password-protected"
) from e
```

---

## 7. 청킹 품질 이슈

### 7.1 SimpleChunker 품질 분석

**문제점**:
1. **크기 불균등**: 한 FAQ가 3,000자, 다른 FAQ는 50자 → 검색 성능 저하
2. **검증 불완전**:
   ```python
   # 첫 번째 항목만 검증
   first_item = document.data[0]
   if not isinstance(first_item, dict):
       raise ValueError("FAQ items must be dictionaries")
   # ❌ 나머지 999개는 검증 안 함
   ```

**개선안**:
```python
# ✅ 모든 항목 검증 (샘플링)
import random
sample_size = min(10, len(document.data))
sample_items = random.sample(document.data, sample_size)
for item in sample_items:
    if not isinstance(item, dict):
        raise ValueError(f"Invalid item type: {type(item)}")
```

### 7.2 PointRuleChunker HTML 파싱 품질

**HTMLTextExtractor** 분석:
```python
def handle_starttag(self, tag: str, attrs):
    if tag == "li":
        self.result.append("\n- ")  # 불릿 포인트 추가
    elif tag == "h4":
        self.result.append("\n### ")  # 마크다운 헤더 변환
```

**우수 사항**: ✅ 구조 보존 (리스트, 헤더)

**개선 필요**:
- 중첩 리스트 처리 (`<ul><ul>`)
- 테이블 파싱 (`<table>`)

---

## 8. 메모리 사용량 문제

### 8.1 병목 지점 분석

**document_processing.py** 메모리 프로파일:
```python
async def process_document_full(self, file_path: str):
    # Phase 1: 로드
    documents = await self.load_document(file_path)  # ~100MB

    # Phase 2: 청킹
    chunks = await self.split_documents(documents)  # ~200MB (원본 + 청크)

    # Phase 3: 임베딩
    embedded_chunks = await self.embed_chunks_parallel(chunks)  # ~400MB (청크 + 임베딩)

    # ❌ 문제: Phase 3 시점에 원본 문서가 여전히 메모리에 존재
    return embedded_chunks
```

**최대 메모리 사용량**: 원본 × 4배

### 8.2 해결 전략

#### 전략 1: 파이프라인 스트리밍
```python
async def process_document_streaming(self, file_path: str):
    async for document in self.load_document_stream(file_path):  # Generator
        chunks = await self.split_document(document)  # 개별 문서 청킹
        for chunk in chunks:
            embedding = await self.embed_chunk(chunk)  # 개별 임베딩
            yield embedding  # 즉시 반환
            # document, chunks는 자동 GC
```

**효과**: 메모리 사용량 1/10 감소

#### 전략 2: 배치 크기 제한
```python
BATCH_SIZE = 50  # 한 번에 50개 청크만 처리

for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i:i+BATCH_SIZE]
    embeddings = await self.embed_chunks(batch)
    await self.store_embeddings(embeddings)
    # batch는 처리 후 해제
```

---

## 9. 종합 평가 및 권장사항

### 9.1 우선순위별 개선 과제

#### 🔴 Critical (즉시 수정)
1. **CSVLoader 인코딩 처리** (심각도: High)
   - 영향: 한글 CSV 파일 처리 실패
   - 해결 시간: 1시간
   - 코드 위치: `csv_loader.py:24`

2. **PointRuleProcessor Factory 미등록** (심각도: High)
   - 영향: `DocumentProcessorFactory.create('point_rule')` 실패
   - 해결 시간: 10분
   - 코드 위치: `factory.py:38`

#### 🟡 High Priority (1주 내)
3. **메모리 스트리밍 처리** (심각도: Medium)
   - 영향: 대용량 파일 처리 시 OOM
   - 해결 시간: 2일
   - 코드 위치: 모든 로더 + `document_processing.py`

4. **오류 메시지 개선** (심각도: Medium)
   - 영향: 디버깅 시간 증가
   - 해결 시간: 1일
   - 코드 위치: 모든 로더

#### 🟢 Medium Priority (1개월 내)
5. **OCR 통합** (심각도: Low)
   - 영향: 스캔 PDF 처리 불가
   - 해결 시간: 1주
   - 코드 위치: `pdf_loader.py`

6. **DOCX 표 추출** (심각도: Low)
   - 영향: 표 중심 문서 정보 손실
   - 해결 시간: 1일
   - 코드 위치: `docx_loader.py`

### 9.2 아키텍처 개선 제안

#### 제안 1: LoaderStrategy에 스트리밍 지원 추가
```python
# base.py
class DocumentLoaderStrategy(ABC):
    @abstractmethod
    async def load(self, file_path: Path) -> list[Document]:
        """기존 배치 로딩"""
        pass

    async def load_stream(self, file_path: Path) -> AsyncIterator[Document]:
        """스트리밍 로딩 (옵션)"""
        # 기본 구현: 배치 로딩 결과를 스트림으로 변환
        documents = await self.load(file_path)
        for doc in documents:
            yield doc
```

#### 제안 2: Validation Layer 추가
```python
# validators/document_validator.py
class DocumentValidator:
    def validate_encoding(self, file_path: Path) -> str:
        """파일 인코딩 자동 감지"""
        import chardet
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']

    def validate_size(self, file_path: Path, max_size_mb: int = 100):
        """파일 크기 검증"""
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValueError(f"File too large: {size_mb:.1f}MB > {max_size_mb}MB")
```

### 9.3 테스트 커버리지 개선

**현재 상태**: 테스트 코드 발견되지 않음

**권장 테스트 케이스**:
```python
# tests/unit/documents/test_loaders.py
@pytest.mark.parametrize("encoding", ["utf-8", "cp949", "euc-kr"])
async def test_csv_loader_encoding(encoding):
    """다양한 인코딩의 CSV 파일 로딩 테스트"""
    # Given: 특정 인코딩의 테스트 CSV
    test_file = create_test_csv(encoding=encoding)

    # When: 로더로 파일 읽기
    loader = CSVLoader()
    documents = await loader.load(test_file)

    # Then: 한글 텍스트 정상 로드
    assert "한글" in documents[0].page_content

@pytest.mark.parametrize("file_size_mb", [1, 10, 100, 500])
async def test_pdf_loader_large_file(file_size_mb):
    """대용량 PDF 파일 메모리 사용량 테스트"""
    # Given: 지정된 크기의 테스트 PDF
    test_pdf = create_test_pdf(size_mb=file_size_mb)

    # When: 로더로 파일 읽기
    loader = PDFLoader()
    with track_memory() as mem:
        documents = await loader.load(test_pdf)

    # Then: 메모리 사용량이 파일 크기의 3배 이하
    assert mem.peak_mb < file_size_mb * 3
```

---

## 10. 결론

### 10.1 강점 (Strengths)
1. ✅ **잘 설계된 아키텍처**: Strategy/Factory 패턴으로 확장 가능
2. ✅ **명확한 책임 분리**: Loader, Chunker, Processor 각각의 역할 명확
3. ✅ **유연한 메타데이터 추출**: 규칙 기반으로 빠른 처리
4. ✅ **로깅 체계 완비**: 모든 주요 동작에 로그 기록

### 10.2 약점 (Weaknesses)
1. ❌ **인코딩 처리 불완전**: CSV/XLSX 한글 처리 위험
2. ❌ **메모리 관리 미흡**: 대용량 파일 처리 불가
3. ❌ **테스트 부재**: 단위 테스트 발견되지 않음
4. ❌ **오류 메시지 부실**: 디버깅 어려움

### 10.3 최종 점수

| 영역 | 점수 | 평가 |
|------|------|------|
| **아키텍처 설계** | 9/10 | 우수한 패턴 적용 |
| **파일 형식 지원** | 7/10 | 주요 형식 지원, OCR 없음 |
| **청킹 품질** | 6/10 | 기본 기능만 구현 |
| **인코딩 처리** | 4/10 | TextLoader만 양호 |
| **메모리 효율** | 3/10 | 스트리밍 미지원 |
| **오류 처리** | 5/10 | 로깅은 있으나 메시지 불명확 |
| **테스트 커버리지** | 1/10 | 테스트 코드 부재 |

**종합 점수**: **5.6/10** (개선 여지 상당)

---

## 부록 A: 파일 매핑

### Documents Module 파일 목록
```
app/modules/core/documents/
├── __init__.py
├── base.py                          # BaseDocumentProcessor
├── factory.py                       # DocumentProcessorFactory
├── document_processing.py           # DocumentProcessor (메인)
├── loaders/
│   ├── __init__.py
│   ├── base.py                     # DocumentLoaderStrategy
│   ├── factory.py                  # LoaderFactory
│   ├── pdf_loader.py               # PDFLoader
│   ├── docx_loader.py              # DOCXLoader
│   ├── xlsx_loader.py              # XLSXLoader
│   ├── csv_loader.py               # CSVLoader ⚠️
│   ├── json_loader.py              # JSONLoader
│   ├── markdown_loader.py          # MarkdownLoader
│   ├── html_loader.py              # HTMLLoader
│   └── text_loader.py              # TextLoader ✅
├── chunking/
│   ├── __init__.py
│   ├── base.py                     # BaseChunker
│   ├── simple_chunker.py           # SimpleChunker
│   └── point_rule_chunker.py       # PointRuleChunker
├── processors/
│   ├── __init__.py
│   ├── faq_processor.py            # FAQProcessor
│   └── point_rule_processor.py     # PointRuleProcessor ⚠️
├── metadata/
│   ├── __init__.py
│   ├── base.py                     # BaseMetadataExtractor
│   └── rule_based.py               # RuleBasedExtractor
└── models/
    ├── __init__.py
    ├── chunk.py                     # Chunk 모델
    └── document.py                  # Document 모델
```

**⚠️ 표시**: 즉시 수정 필요
**✅ 표시**: 모범 사례

---

**보고서 작성 완료**
**다음 단계**: Critical 이슈 수정 → High Priority 이슈 해결 → 테스트 코드 작성
