from contracts.schemas import ErrorBody, ErrorResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(code: str, message: str) -> ErrorResponse:
    return ErrorResponse(error=ErrorBody(code=code, message=message))



def install_error_handlers(app) -> None:
    """Every non-2xx response uses the contract shape {"error": {"code", "message"}} (no stack traces)."""
    import logging

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException

    log = logging.getLogger("backend.errors")

    def body(code: str, message: str, status: int) -> JSONResponse:
        return JSONResponse(status_code=status, content=error_response(code, message).model_dump())

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return body(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return body("validation_error", f"{where}: {first.get('msg', 'invalid request')}".strip(": "), 422)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException):
        return body("not_found" if exc.status_code == 404 else "http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return body("internal_error", "Something went wrong. Please try again.", 500)
