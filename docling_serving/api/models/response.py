from enum import Enum
from typing import Optional

from docling_core.types import DoclingDocument
from pydantic import BaseModel


class ConversionStatus(str, Enum):
    PENDING = "pending"
    STARTED = "started"
    FAILURE = "failure"
    SUCCESS = "success"


class ConvertResponse(BaseModel):
    id: str
    filename: str
    md_content: Optional[str] = None
    json_content: Optional[DoclingDocument] = None
    text_content: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    status: ConversionStatus
    result: Optional[ConvertResponse] = None


class JobSummary(BaseModel):
    id: str
    status: ConversionStatus
