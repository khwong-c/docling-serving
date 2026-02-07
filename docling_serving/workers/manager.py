import os
import threading
from hashlib import sha1
from pathlib import Path

from docling.datamodel.backend_options import PdfBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ConvertPipelineOptions, PdfPipelineOptions, PdfBackend
from docling.document_converter import PdfFormatOption, DocumentConverter, HTMLFormatOption, ImageFormatOption
from docling.models.factories import get_ocr_factory

from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from docling.backend.image_backend import ImageDocumentBackend

from ..api.models.request import PipelineType
from ..settings import docling_serve_settings


class ConverterManager:
    def __init__(
            self,
            artifacts_path: Path | None,
            # config: DoclingConverterManagerConfig,
    ):
        if artifacts_path is None:
            artifacts_path = Path(os.getcwd()) / ".models"
            artifacts_path.mkdir(parents=True, exist_ok=True)
        self.artifacts_path = artifacts_path
        self.ocr_factory = get_ocr_factory()
        self._cache_lock = threading.Lock()
        self._cache: dict[str, DocumentConverter] = {}

    @staticmethod
    def _get_option_hash(option: PdfPipelineOptions | ConvertPipelineOptions) -> str:
        # Can be simplified to specific fields
        j = option.model_dump_json().encode()
        return sha1(j).hexdigest()

    @staticmethod
    def _create_converter(
            pipeline_type: PipelineType,
            pipeline_option: PdfPipelineOptions | ConvertPipelineOptions,
            pdf_backend: PdfBackend | None,
    ) -> DocumentConverter:
        if pipeline_type == PipelineType.HTML:
            convertor = DocumentConverter(
                allowed_formats=[InputFormat.HTML],
                format_options={
                    InputFormat.HTML: HTMLFormatOption(pipeline_options=pipeline_option)
                }
            )
            convertor.initialize_pipeline(InputFormat.HTML)
            return convertor

        if pipeline_type == PipelineType.PDF:
            pdf_class = {
                PdfBackend.DLPARSE_V1: DoclingParseDocumentBackend,
                PdfBackend.DLPARSE_V2: DoclingParseV2DocumentBackend,
                PdfBackend.DLPARSE_V4: DoclingParseV4DocumentBackend,
                PdfBackend.PYPDFIUM2: PyPdfiumDocumentBackend,
            }.get(pdf_backend)

            if pdf_class is None:
                raise Exception(f"Unsupported pipeline option type: {type(pipeline_option)}")

            convertor = DocumentConverter(
                allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_option,
                        backend=pdf_class,
                        backend_options=PdfBackendOptions(),
                    ),
                    InputFormat.IMAGE: ImageFormatOption(
                        pipeline_options=pipeline_option,
                        backend=ImageDocumentBackend,
                        backend_options=PdfBackendOptions(),
                    ),
                }
            )
            convertor.initialize_pipeline(InputFormat.PDF)
            convertor.initialize_pipeline(InputFormat.IMAGE)
            return convertor

        raise ValueError("Unsupported pipeline type")

    def get_converter(
            self,
            pipeline_type: PipelineType,
            pipeline_option: PdfPipelineOptions | ConvertPipelineOptions,
            pdf_backend: PdfBackend | None,
    ) -> DocumentConverter:
        pipeline_option.artifacts_path = self.artifacts_path
        options_hash = f"{self._get_option_hash(pipeline_option)}-{pdf_backend}"

        with self._cache_lock:
            converter = self._cache.get(options_hash)
            if converter is None:
                converter = self._cache[options_hash] = self._create_converter(
                    pipeline_type, pipeline_option, pdf_backend,
                )
        return converter


# Singleton
manager = ConverterManager(docling_serve_settings.artifacts_path)
