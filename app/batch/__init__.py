"""
데이터 동기화 및 배치 시스템

주요 모듈:
- crawler: Playwright 기반 HTML 크롤러
- parser: BeautifulSoup4 기반 파싱 및 청킹
- validator: 5단계 데이터 검증 시스템
- scheduler: APScheduler 기반 스케줄러 (매일 05:00 KST)
- main: 메인 실행 오케스트레이터
"""

__version__ = "0.1.0"
