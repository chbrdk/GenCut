# utils/error_handler.py
import logging
from fastapi import HTTPException
from typing import Any, Dict

logger = logging.getLogger(__name__)

class GenCutException(Exception):
    """Base exception for GenCut services"""
    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class VideoProcessingError(GenCutException):
    """Error during video processing"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, 422, details)

class ModelNotLoadedError(GenCutException):
    """Error when AI models are not loaded"""
    def __init__(self, message: str = "AI models are not loaded"):
        super().__init__(message, 503)

class FileNotFoundError(GenCutException):
    """Error when file is not found"""
    def __init__(self, file_path: str):
        super().__init__(f"File not found: {file_path}", 404, {"file_path": file_path})

def handle_exception(e: Exception) -> HTTPException:
    """Convert exceptions to HTTP exceptions with proper logging"""
    if isinstance(e, GenCutException):
        logger.error(f"GenCut error: {e.message}", extra=e.details)
        return HTTPException(status_code=e.status_code, detail=e.message)
    
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return HTTPException(status_code=500, detail="Internal server error")
