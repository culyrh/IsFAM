from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException carrying the spec's `error_code` field in the response body."""

    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(status_code=status_code, detail={"error_code": error_code, "message": message})
