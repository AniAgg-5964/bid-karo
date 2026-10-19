class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found.") -> None:
        super().__init__(404, detail)


class ConflictError(AppError):
    def __init__(self, detail: str = "Resource already exists.") -> None:
        super().__init__(409, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "You do not have access to this resource.") -> None:
        super().__init__(403, detail)


class ValidationError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(422, detail)


class NotConfiguredError(AppError):
    def __init__(self, detail: str = "Integration is not configured.") -> None:
        super().__init__(503, detail)


class UpstreamError(AppError):
    def __init__(self, detail: str = "Upstream service failed.") -> None:
        super().__init__(502, detail)
