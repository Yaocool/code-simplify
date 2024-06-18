
from typing import Any


class BaseResponse:
    code: int
    data: Any

    def __init__(self, code: int, data: Any = None):
        self.code = code
        self.data = data
