"""
MongoDB Atlas 연결 및 관리 모듈

주요 기능:
- MongoDB Atlas 클라우드 데이터베이스 연결
- 세션 및 대화 기록 컬렉션 관리
- 연결 풀링 및 재시도 로직
- 에러 핸들링 및 로깅

의존성:
- pymongo: MongoDB 공식 Python 드라이버
- app.lib.config_loader: 설정 파일 로드
- app.lib.logger: 구조화된 로깅
"""

from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    ServerSelectionTimeoutError,
)

from app.lib.config_loader import load_config
from app.lib.logger import get_logger

# 로거 설정
logger = get_logger(__name__)


class MongoDBClient:
    """
    MongoDB Atlas 클라이언트 싱글톤 클래스

    애플리케이션 전체에서 하나의 MongoDB 연결 인스턴스를 공유합니다.
    연결 풀링을 통해 효율적인 리소스 관리를 제공합니다.

    Attributes:
        _instance: 싱글톤 인스턴스
        _client: MongoClient 인스턴스
        _db: Database 인스턴스
        _config: MongoDB 설정 정보
    """

    _instance: MongoDBClient | None = None
    _client: MongoClient | None = None
    _db: Database | None = None
    _config: dict | None = None

    def __new__(cls) -> MongoDBClient:
        """싱글톤 패턴 구현 - 하나의 인스턴스만 생성"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """MongoDB 클라이언트 초기화"""
        # 이미 초기화된 경우 스킵
        if self._client is not None:
            return

        try:
            # 설정 로드
            config = load_config()
            self._config = config.get("mongodb", {})

            if not self._config or not self._config.get("uri"):
                logger.warning("MongoDB 설정이 없습니다. MongoDB 기능이 비활성화됩니다.")
                return

            # MongoDB 연결 설정
            connection_options = {
                "maxPoolSize": self._config.get("max_pool_size", 10),
                "minPoolSize": self._config.get("min_pool_size", 1),
                "retryWrites": self._config.get("retry_writes", True),
                "w": self._config.get("w", "majority"),
                "serverSelectionTimeoutMS": int(self._config.get("timeout_ms", 5000)),
            }

            # MongoClient 생성
            self._client = MongoClient(self._config["uri"], **connection_options)

            # 데이터베이스 선택
            db_name = self._config.get("database", "chatbot")
            self._db = self._client[db_name]

            # 연결 테스트
            self._client.admin.command("ping")

            logger.info(
                "MongoDB Atlas 연결 성공",
                extra={
                    "database": db_name,
                    "max_pool_size": connection_options["maxPoolSize"],
                    "timeout_ms": connection_options["serverSelectionTimeoutMS"],
                },
            )

        except ConnectionFailure as e:
            logger.error(
                "MongoDB 연결 실패",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "suggestion": (
                        "1. MONGODB_URI 환경 변수가 올바른지 확인하세요\n"
                        "2. MongoDB Atlas 클러스터가 실행 중인지 확인하세요\n"
                        "3. 네트워크 IP 화이트리스트 설정을 확인하세요 (Atlas > Network Access)\n"
                        "4. 사용자 인증 정보가 올바른지 확인하세요\n"
                        "5. connection string 형식: mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<dbname>"
                    ),
                },
            )
            self._client = None
            self._db = None

        except ServerSelectionTimeoutError as e:
            logger.error(
                "MongoDB 서버 선택 타임아웃",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timeout_ms": connection_options.get("serverSelectionTimeoutMS", 5000),
                    "suggestion": (
                        "1. MongoDB Atlas 클러스터가 실행 중인지 확인하세요\n"
                        "2. 클러스터가 일시 중지 상태가 아닌지 확인하세요 (Atlas > Clusters)\n"
                        "3. 네트워크 연결 상태를 확인하세요\n"
                        "4. IP 화이트리스트에 현재 IP가 포함되어 있는지 확인하세요\n"
                        "5. 방화벽이 포트 27017 (MongoDB)을 차단하지 않는지 확인하세요"
                    ),
                },
            )
            self._client = None
            self._db = None

        except ConfigurationError as e:
            logger.error(
                "MongoDB 설정 오류",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "suggestion": (
                        "1. MONGODB_URI 형식이 올바른지 확인하세요\n"
                        "2. 올바른 형식: mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<dbname>\n"
                        "3. 특수 문자가 포함된 비밀번호는 URL 인코딩이 필요합니다\n"
                        "4. 예시: mongodb+srv://user:p%40ssw0rd@cluster.mongodb.net/chatbot\n"
                        "5. Atlas 대시보드에서 정확한 connection string을 복사하세요"
                    ),
                },
            )
            self._client = None
            self._db = None

        except Exception as e:
            logger.error(
                "MongoDB 초기화 중 예상치 못한 오류 발생",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            self._client = None
            self._db = None

    @property
    def client(self) -> MongoClient | None:
        """
        MongoClient 인스턴스 반환

        Returns:
            MongoClient 인스턴스 또는 None (연결 실패 시)
        """
        return self._client

    @property
    def db(self) -> Database | None:
        """
        Database 인스턴스 반환

        Returns:
            Database 인스턴스 또는 None (연결 실패 시)
        """
        return self._db

    def get_collection(self, collection_name: str) -> Collection | None:
        """
        지정된 이름의 컬렉션 반환

        Args:
            collection_name: 컬렉션 이름

        Returns:
            Collection 인스턴스 또는 None (연결 실패 시)

        Example:
            sessions = mongodb_client.get_collection("sessions")
            sessions.insert_one({"session_id": "123", "data": {...}})
        """
        if self._db is None:
            logger.warning(
                "MongoDB 연결이 없어 컬렉션을 가져올 수 없습니다.",
                extra={"collection_name": collection_name},
            )
            return None

        return self._db[collection_name]

    def get_sessions_collection(self) -> Collection | None:
        """
        세션 컬렉션 반환

        Returns:
            세션 Collection 인스턴스 또는 None
        """
        collections_config = self._config.get("collections", {}) if self._config else {}
        collection_name = collections_config.get("sessions", "sessions")
        return self.get_collection(collection_name)

    def get_chat_history_collection(self) -> Collection | None:
        """
        대화 기록 컬렉션 반환

        Returns:
            대화 기록 Collection 인스턴스 또는 None
        """
        collections_config = self._config.get("collections", {}) if self._config else {}
        collection_name = collections_config.get("chat_history", "chat_history")
        return self.get_collection(collection_name)

    def ping(self) -> bool:
        """
        MongoDB 연결 상태 확인

        Returns:
            연결 성공 시 True, 실패 시 False
        """
        if self._client is None:
            return False

        try:
            self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.error("MongoDB ping 실패", extra={"error": str(e)})
            return False

    def close(self) -> None:
        """
        MongoDB 연결 종료

        Note:
            일반적으로 애플리케이션 종료 시에만 호출됩니다.
            pymongo는 자동으로 연결 풀을 관리하므로 명시적 종료가 필요하지 않습니다.
        """
        if self._client is not None:
            self._client.close()
            logger.info("MongoDB 연결이 종료되었습니다.")
            self._client = None
            self._db = None


# 싱글톤 인스턴스 생성
mongodb_client = MongoDBClient()
