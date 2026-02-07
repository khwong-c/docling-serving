from enum import Enum
from typing import Annotated, Literal, Optional

from docling.datamodel.pipeline_options import PdfPipelineOptions, ConvertPipelineOptions, PdfBackend
from docling.datamodel.settings import PageRange, DEFAULT_PAGE_RANGE
from pydantic import BaseModel, Field, AnyHttpUrl
from docling.datamodel.base_models import OutputFormat


class FileSource(BaseModel):
    kind: Literal["file"] = "file"
    base64_string: Annotated[
        str,
        Field(
            description="Content of the file serialized in base64. "
                        "For example it can be obtained via "
                        "`base64 -w 0 /path/to/file/pdf-to-convert.pdf`."
        ),
    ]
    filename: Annotated[
        str,
        Field(description="Filename of the uploaded document", examples=["file.pdf"]),
    ]


class HttpSource(BaseModel):
    kind: Literal["http"] = "http"
    url: Annotated[
        AnyHttpUrl,
        Field(
            description="HTTP url to process",
            examples=["https://arxiv.org/pdf/2206.01062"],
        ),
    ]
    headers: Annotated[
        dict[str, str],
        Field(
            description="Additional headers used to fetch the urls, "
                        "e.g. authorization, agent, etc"
        ),
    ] = {}


class InlineOutput(BaseModel):
    kind: Literal["inline"] = "inline"


class PipelineType(str, Enum):
    PDF = "pdf"
    HTML = "html"


class InputType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    HTML = "html"


class ConvertOptions(BaseModel):
    pipeline_type: PipelineType = PipelineType.PDF
    pdf_engine: PdfBackend = PdfBackend.DLPARSE_V4
    pdf_pipeline: Optional[PdfPipelineOptions] = PdfPipelineOptions()
    html_pipeline: Optional[ConvertPipelineOptions] = ConvertPipelineOptions()


class ConvertRequest(BaseModel):
    source: Annotated[
        FileSource | HttpSource,
        Field(discriminator="kind"),
    ]

    options: Annotated[
        ConvertOptions,
        Field(
            description="Options for converting",
        ),
    ] = ConvertOptions()

    # input_format: Annotated[
    #     InputType,
    #     Field(
    #         description="Input file type of the conversion",
    #         examples=[InputType.PDF, InputType.IMAGE, InputType.HTML],
    #     ),
    # ] = InputType.PDF

    page_range: Annotated[
        PageRange,
        Field(
            description="Only convert a range of pages. The page number starts at 1.",
            examples=[DEFAULT_PAGE_RANGE, (1, 4)],
        ),
    ] = DEFAULT_PAGE_RANGE

    target: Annotated[
        InlineOutput,
        Field(
            discriminator="kind",
            description="Output target of the conversion",
            examples=["inline"],
        ),
    ] = InlineOutput()

    output_formats: Annotated[
        list[OutputFormat],
        Field(
            description=(
                "Output format(s) to convert to. String or list of strings. "
                f"Allowed values: {', '.join([v.value for v in OutputFormat])}. "
                "Optional, defaults to Markdown."
            ),
            examples=[
                [OutputFormat.MARKDOWN],
                [OutputFormat.MARKDOWN, OutputFormat.JSON],
                [v.value for v in OutputFormat],
            ],
        ),
    ] = [OutputFormat.MARKDOWN]
