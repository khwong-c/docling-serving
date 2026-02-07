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


class DoclingServeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCLING_SERVING_",
        # env_file=".env",
        env_parse_none_str="",
        extra="allow",
    )
    artifacts_path: Optional[Path] = None


uvicorn_settings = UvicornSettings()
docling_serve_settings = DoclingServeSettings()
