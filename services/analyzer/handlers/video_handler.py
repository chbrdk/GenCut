# handlers/video_handler.py
import os
import uuid
import asyncio
from typing import Dict, Any
from fastapi import UploadFile
from ..utils.error_handler import VideoProcessingError, FileNotFoundError, handle_exception
from ..config import UPLOAD_DIR, OUTPUT_DIR
from ..scene_utils import analyze_scenes
from ..visual_analysis import visual_analyzer

async def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file and return the file path"""
    try:
        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp4'
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        return file_path
    except Exception as e:
        raise VideoProcessingError(f"Failed to save uploaded file: {str(e)}")

async def analyze_video_file(file_path: str) -> Dict[str, Any]:
    """Analyze video file and return scene information"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        
        # Analyze scenes
        scenes = analyze_scenes(file_path)
        
        # Generate video ID and filename
        video_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        
        return {
            "video_id": video_id,
            "filename": filename,
            "scenes": scenes
        }
    except Exception as e:
        raise VideoProcessingError(f"Failed to analyze video: {str(e)}")

async def analyze_video_with_ai(file_path: str) -> Dict[str, Any]:
    """Analyze video with AI models"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        
        # Analyze scenes
        scenes = analyze_scenes(file_path)
        
        # Analyze each scene with AI
        for scene in scenes:
            if scene.get('screenshots'):
                for screenshot in scene['screenshots']:
                    screenshot_path = screenshot['url'].replace('/videos/', '/app/videos/')
                    if os.path.exists(screenshot_path):
                        analysis = await visual_analyzer.analyze_image(screenshot_path)
                        screenshot['ai_analysis'] = analysis
        
        # Generate video ID and filename
        video_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        
        return {
            "video_id": video_id,
            "filename": filename,
            "scenes": scenes
        }
    except Exception as e:
        raise VideoProcessingError(f"Failed to analyze video with AI: {str(e)}")
