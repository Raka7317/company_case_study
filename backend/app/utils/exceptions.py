class AppError(Exception):
    """Base application error carrying an HTTP status and error code."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnsupportedFileTypeError(AppError):
    def __init__(self, message="Only PDF / JPG / PNG documents are supported."):
        super().__init__("UNSUPPORTED_FILE_TYPE", message, 415)


class CorruptedFileError(AppError):
    def __init__(self, message="The uploaded file is empty or corrupted."):
        super().__init__("CORRUPTED_FILE", message, 400)


class PageLimitExceededError(AppError):
    def __init__(self, message="Document exceeds the maximum allowed page count."):
        super().__init__("PAGE_LIMIT_EXCEEDED", message, 400)


class DocumentNotFoundError(AppError):
    def __init__(self, message="No processed document found with that name."):
        super().__init__("DOCUMENT_NOT_FOUND", message, 404)


class ProcessingError(AppError):
    def __init__(self, message="Document processing failed."):
        super().__init__("PROCESSING_ERROR", message, 500)
