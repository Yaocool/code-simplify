__all__ = [
    "Error", "InternalError", "OtherInternalError",  "RequestTimeoutError",
    "BadRequestError", "SSEHandlerError"
]


class Error(Exception):
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message

    def __str__(self):
        return f"{self.error_code}: {self.error_message}"

    def __repr__(self):
        return self.__str__()


class InternalError(Error):
    def __init__(self, error_message: str):
        super().__init__(500, error_message)


class OtherInternalError(Error):
    def __init__(self, error_code: int, error_message: str):
        super().__init__(error_code, error_message)


class RequestTimeoutError(Error):
    def __init__(self, error_message: str):
        super().__init__(408, error_message)


class BadRequestError(Error):
    def __init__(self, error_message: str):
        super().__init__(400, error_message)


class SSEHandlerError(Error):
    def __init__(self, error_code: int = 500, error_message: str = ''):
        super().__init__(error_code, error_message)


class RemoteServiceError(Error):
    def __init__(self, error_code: int = 500, error_message: str = ''):
        super().__init__(error_code, error_message)
