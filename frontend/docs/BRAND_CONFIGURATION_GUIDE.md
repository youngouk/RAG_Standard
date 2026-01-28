# 브랜드 설정 가이드

## 개요

프로젝트의 브랜드 관련 설정(컬러, 로고, 앱명 등)을 중앙화하여 수정의 용이성을 높였습니다.

## 주요 개선 사항

### 1. 브랜드 설정 파일 생성 (`src/config/brand.ts`)

모든 브랜드 관련 설정을 한 곳에서 관리합니다:

- **앱 이름**: `BRAND_CONFIG.appName`
- **로고 경로**: `BRAND_CONFIG.logo.favicon`, `BRAND_CONFIG.logo.iconPath`
- **컬러 팔레트**: `BRAND_CONFIG.colors.*`
- **그라디언트**: `BRAND_CONFIG.gradients.*`
- **그림자**: `BRAND_CONFIG.shadows.*`

### 2. 테마 중복 제거

이전에는 `PromptsPage`, `AnalysisPage`, `AdminDashboard`에서 각각 테마를 정의했지만, 이제 모든 페이지에서 `createAppTheme()` 함수를 사용하여 통일된 테마를 사용합니다.

### 3. 하드코딩된 컬러값 제거

컴포넌트에 직접 하드코딩되어 있던 컬러값을 모두 `BRAND_CONFIG`에서 참조하도록 변경했습니다.

### 4. 브랜드명 중앙화

브랜드명이 여러 곳에 하드코딩되어 있던 것을 `BRAND_CONFIG.appName`과 `getPageTitle()` 헬퍼 함수를 사용하도록 변경했습니다.

## 사용 방법

### 컬러 변경하기

`src/config/brand.ts` 파일을 열어 컬러 값을 수정하세요:

```typescript
colors: {
  primary: {
    main: '#1a1a1a', // 여기를 원하는 컬러로 변경
    light: '#404040',
    dark: '#000000',
  },
  // ...
}
```

### 로고 변경하기

1. 새 로고 파일을 `public/` 디렉토리에 추가
2. `src/config/brand.ts`에서 경로 수정:

```typescript
logo: {
  favicon: '/your-new-logo.svg',
  iconPath: '/your-new-logo.svg',
  alt: 'Your Brand Logo',
}
```

### 앱 이름 변경하기

`src/config/brand.ts`에서 수정:

```typescript
appName: 'Your New App Name',
appTitle: 'Your New App Title',
```

### 그라디언트 변경하기

```typescript
gradients: {
  primary: 'linear-gradient(135deg, #YOUR_COLOR_1 0%, #YOUR_COLOR_2 100%)',
  primaryHover: 'linear-gradient(135deg, #YOUR_COLOR_2 0%, #YOUR_COLOR_3 100%)',
}
```

## 헬퍼 함수

### `getPageTitle(pageName?: string)`

페이지 제목을 생성하는 헬퍼 함수입니다:

```typescript
import { getPageTitle } from '../config/brand';

// 사용 예시
<Typography>{getPageTitle('챗봇')}</Typography>
// 결과: "OneRAG - 챗봇"
```

### `getColor(colorPath: string, darkMode: boolean)`

컬러 경로를 통해 컬러 값을 가져오는 함수입니다 (고급 사용):

```typescript
import { getColor } from '../config/brand';

const primaryColor = getColor('primary.main', false);
```

## 변경된 파일 목록

- ✅ `src/config/brand.ts` (신규 생성)
- ✅ `src/theme/index.ts` (브랜드 설정 사용)
- ✅ `src/pages/PromptsPage.tsx` (테마 중복 제거, 브랜드 설정 사용)
- ✅ `src/pages/AnalysisPage.tsx` (테마 중복 제거, 브랜드 설정 사용)
- ✅ `src/pages/Admin/AdminDashboard.tsx` (테마 중복 제거, 브랜드 설정 사용)
- ✅ `src/pages/ChatPage.tsx` (브랜드 설정 사용)
- ✅ `src/pages/UploadPage.tsx` (브랜드 설정 사용)
- ✅ `src/App.tsx` (브랜드 설정 사용)

## 장점

1. **수정 용이성**: 한 파일만 수정하면 전체 앱에 반영
2. **일관성**: 모든 페이지에서 동일한 브랜드 설정 사용
3. **유지보수성**: 중복 코드 제거로 유지보수 용이
4. **확장성**: 새로운 브랜드 설정 추가가 쉬움

## 주의사항

- 브랜드 설정을 변경한 후에는 개발 서버를 재시작하는 것을 권장합니다
- 컬러 값을 변경할 때는 접근성(색상 대비)을 고려하세요
- 로고 파일은 `public/` 디렉토리에 있어야 합니다

