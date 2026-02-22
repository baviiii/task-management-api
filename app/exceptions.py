from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else "HTTP Error", "details": {}},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        details[field] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Failed", "details": details},
    )
