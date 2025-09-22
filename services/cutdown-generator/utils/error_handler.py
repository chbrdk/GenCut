# utils/error_handler.py
import logging
from flask import jsonify
from typing import Any, Dict

logger = logging.getLogger(__name__)

class GenCutException(Exception):
    """Base exception for GenCut services"""
    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class UploadError(GenCutException):
    """Error during file upload"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, 422, details)

class ElevenLabsError(GenCutException):
    """Error with ElevenLabs API"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, 502, details)

class FileNotFoundError(GenCutException):
    """Error when file is not found"""
    def __init__(self, file_path: str):
        super().__init__(f"File not found: {file_path}", 404, {"file_path": file_path})

def handle_exception(e: Exception):
    """Convert exceptions to Flask responses with proper logging"""
    if isinstance(e, GenCutException):
        logger.error(f"GenCut error: {e.message}", extra=e.details)
        return jsonify({
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details
        }), e.status_code
    
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "status_code": 500
    }), 500

def register_error_handlers(app):
    """Register error handlers with Flask app"""
    
    @app.errorhandler(GenCutException)
    def handle_gencut_exception(e: GenCutException):
        return handle_exception(e)
    
    @app.errorhandler(Exception)
    def handle_unexpected_exception(e: Exception):
        return handle_exception(e)
