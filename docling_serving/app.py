import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

from .api import (
    router_health,
    router_convert,
    router_tasks,
    router_clear,
)
from .workers.work_queue_local import LocalQueue
from .api.dependencies import create_queue


# Set up custom logging as we'll be intermixes with FastAPI/Uvicorn's logging
class ColoredLogFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.DEBUG: "\033[94m",  # Blue
        logging.INFO: "\033[92m",  # Green
        logging.WARNING: "\033[93m",  # Yellow
        logging.ERROR: "\033[91m",  # Red
        logging.CRITICAL: "\033[95m",  # Magenta
    }
    RESET_CODE = "\033[0m"

    def format(self, record):
        color = self.COLOR_CODES.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{self.RESET_CODE}"
        return super().format(record)


class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        return json.dumps({
            "level": str(record.levelname),
            "name": str(record.name),
            "time": self.formatTime(record, self.datefmt),
            "message": msg,
        })


logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(levelname)s:\t%(asctime)s - %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

# Override the formatter with the custom ColoredLogFormatter
root_logger = logging.getLogger()  # Get the root logger
for handler in root_logger.handlers:  # Iterate through existing handlers
    # handler.setFormatter(JSONLogFormatter("%(message)s"))
    if handler.formatter:
        handler.setFormatter(ColoredLogFormatter(handler.formatter._fmt))

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.job_queue = create_queue()
    asyncio.create_task(app.job_queue.start_worker())
    yield
    await app.job_queue.shutdown()


def create_app():
    app = FastAPI(
        title="Docling Serve",
        docs_url="/swagger",
        redoc_url="/docs",
        lifespan=lifespan,
    )
    app.include_router(router_health)
    app.include_router(router_convert)
    app.include_router(router_tasks)
    # app.include_router(router_clear)
    return app


app = create_app()
