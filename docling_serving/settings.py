import enum
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class UvicornSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UVICORN_",
        # env_file=".env",
        extra="allow",
    )

    host: str = "0.0.0.0"
    port: int = 5001
    reload: bool = False


class AsyncEngine(str, enum.Enum):
    LOCAL = "local"
    # KFP = "kfp"
    RQ = "rq"


class RQSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    queue_name: str = "docling_serving"


class JobSettings(BaseSettings):
    clean_after_retrieve: bool = False
    clean_after_interval: int = 60
    force_clean_after_interval: int = 7200


class DoclingServeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCLING_SERVING_",
        # env_file=".env",
        env_nested_delimiter='__',
        env_parse_none_str="",
        extra="allow",
    )
    artifacts_path: Optional[Path] = None
    job_settings: JobSettings = JobSettings()

    async_engine: AsyncEngine = AsyncEngine.LOCAL
    rq_settings: RQSettings = RQSettings()
    concurrent_workers: int = 2


uvicorn_settings = UvicornSettings()
docling_serve_settings = DoclingServeSettings()
