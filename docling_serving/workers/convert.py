import base64
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from docling.datamodel.base_models import OutputFormat
from docling_core.types import DoclingDocument
from docling_core.types.io import DocumentStream
from docling_core.utils.file import resolve_source_to_path, resolve_source_to_stream
from pydantic import AnyHttpUrl, BaseModel

from ..api.models.request import ConvertRequest, PipelineType, HttpSource, FileSource

from .manager import manager


class ConvertedResult(BaseModel):
    filename: str
    md_content: Optional[str] = None
    json_content: Optional[DoclingDocument] = None
    text_content: Optional[str] = None


def convert(
        req: ConvertRequest
) -> ConvertedResult:
    raise Exception("Fugu!")
    pipe_type = req.options.pipeline_type
    engine, pipe_option = None, req.options.html_pipeline
    if pipe_type == PipelineType.PDF:
        engine, pipe_option = req.options.pdf_engine, req.options.pdf_pipeline
    convertor = manager.get_converter(
        pipe_type, pipe_option, engine,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        headers = {}
        src: DocumentStream | Path | None = None
        fname: str | AnyHttpUrl = ""
        if isinstance(req.source, HttpSource):
            headers = req.source.headers
            fname = req.source.url.unicode_string()
            src = resolve_source_to_path(
                req.source.url,
                headers,
                workdir=Path(tmpdir)
            )
        if isinstance(req.source, FileSource):
            src = DocumentStream(
                name=(fname := req.source.filename or "temp-file"),
                stream=BytesIO(base64.b64decode(req.source.base64_string)),
            )
        if src is None:
            raise ValueError("Source cannot be None")

        converted = convertor.convert(
            source=src,
            headers=headers,
            page_range=req.page_range,
        )
        resp = ConvertedResult(
            filename=fname,
            md_content=None,
            json_content=None,
            text_content=None,
        )
        if OutputFormat.MARKDOWN in req.output_formats:
            resp.md_content = converted.document.export_to_markdown()
        if OutputFormat.JSON in req.output_formats:
            resp.json_content = converted.document
        if OutputFormat.TEXT in req.output_formats:
            resp.text_content = converted.document.export_to_text()
        return resp
