# -----------------------------------------------------------------------------
# CPU Runtime
# -----------------------------------------------------------------------------
FROM ubuntu:24.04 AS runtime-cpu

ENV TZ=US \
    DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1

# Install Python 3.12 and prerequestics
RUN chmod 1777 /tmp
RUN apt update && apt install -y \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv python install 3.12

WORKDIR /app

COPY pyproject.toml ./

# Install CPU dependencies
RUN uv venv && uv pip install setuptools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --group cpu --extra rapidocr

COPY docling_serving /app/docling_serving

RUN mkdir -p /app/artifacts

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=5001

EXPOSE 5001

CMD ["uv", "run", "--no-project", "uvicorn", "docling_serving.app:app", "--host", "0.0.0.0", "--port", "5001"]

# -----------------------------------------------------------------------------
# CUDA 12.6 Runtime
# -----------------------------------------------------------------------------
FROM nvcr.io/nvidia/cuda:12.6.3-base-ubuntu24.04 AS runtime-cu126

ENV TZ=US \
    DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1

# Install Python 3.12 and prerequestics
RUN chmod 1777 /tmp
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv python install 3.12

WORKDIR /app

COPY pyproject.toml ./

# Install CUDA 12.6 dependencies
RUN uv venv && uv pip install setuptools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --group cu126 --extra rapidocr

# Other OCR Options
# uv sync --no-dev --group cu126 --extra tesserocr --extra easyocr --extra rapidocrgpu
# Flash Attention installation and setup
#RUN curl -L https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl \
#    -o flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    uv pip install flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    rm flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl
#ENV DOCLING_CUDA_USE_FLASH_ATTENTION2=1

COPY docling_serving /app/docling_serving

RUN mkdir -p /app/artifacts

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=5001

EXPOSE 5001

CMD ["uv", "run", "--no-project", "uvicorn", "docling_serving.app:app", "--host", "0.0.0.0", "--port", "5001"]

## -----------------------------------------------------------------------------
## CUDA 12.8 Runtime
## -----------------------------------------------------------------------------
FROM nvcr.io/nvidia/cuda:12.8.1-base-ubuntu24.04 AS runtime-cu128

ENV TZ=US \
    DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1

# Install Python 3.12 and prerequestics
RUN chmod 1777 /tmp
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv python install 3.12

WORKDIR /app

COPY pyproject.toml ./

# Install CUDA 12.8 dependencies
RUN uv venv && uv pip install setuptools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --group cu128 --extra rapidocr

# Other OCR Options
# uv sync --no-dev --group cu126 --extra tesserocr --extra easyocr --extra rapidocrgpu
# Flash Attention installation and setup
#RUN curl -L https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl \
#    -o flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    uv pip install flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    rm flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl
#ENV DOCLING_CUDA_USE_FLASH_ATTENTION2=1

COPY docling_serving /app/docling_serving

RUN mkdir -p /app/artifacts

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=5001

EXPOSE 5001

CMD ["uv", "run", "--no-project", "uvicorn", "docling_serving.app:app", "--host", "0.0.0.0", "--port", "5001"]

## -----------------------------------------------------------------------------
## CUDA 12.8 Runtime
## -----------------------------------------------------------------------------
FROM nvcr.io/nvidia/cuda:13.0.2-base-ubuntu24.04 AS runtime-cu130

ENV TZ=US \
    DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_DEV=1

# Install Python 3.12 and prerequestics
RUN chmod 1777 /tmp
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv python install 3.12

WORKDIR /app

COPY pyproject.toml ./

# Install CUDA 13.0 dependencies
RUN uv venv && uv pip install setuptools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --group cu130 --extra rapidocr

# Other OCR Options
# uv sync --no-dev --group cu126 --extra tesserocr --extra easyocr --extra rapidocrgpu
# Flash Attention installation and setup
#RUN curl -L https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl \
#    -o flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    uv pip install flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
#    rm flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl
#ENV DOCLING_CUDA_USE_FLASH_ATTENTION2=1

COPY docling_serving /app/docling_serving

RUN mkdir -p /app/artifacts

ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=5001

EXPOSE 5001

CMD ["uv", "run", "--no-project", "uvicorn", "docling_serving.app:app", "--host", "0.0.0.0", "--port", "5001"]