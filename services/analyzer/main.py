# main_new.py - Refactored analyzer service
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import asyncio
from typing import List

# Import our modular components
from config import UPLOAD_DIR, OUTPUT_DIR, SEPARATED_DIR, MODELS_LOADED
from models.requests import (
    VideoPathRequest, TranscribeRequest, CutdownRequest, 
    ScenesRequest, CompilationRequest, CutdownV2Request
)
from handlers.video_handler import analyze_video_file, analyze_video_with_ai, save_uploaded_file
from handlers.cutdown_handler import generate_cutdown_v2, separate_video_audio_handler
from utils.error_handler import handle_exception, ModelNotLoadedError
from visual_analysis import visual_analyzer
from ffmpeg_utils import cut_clip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GenCut Analyzer API",
    description="Video-Analyse und KI-basierte Szenen-Erkennung",
    version="1.0.0"
)

# Mount the videos directory to serve static files
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

@app.on_event("startup")
async def startup_event():
    """Initialize AI models on startup"""
    global MODELS_LOADED
    try:
        await visual_analyzer.initialize()
        MODELS_LOADED = True
        logger.info("AI models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load AI models: {e}")
        MODELS_LOADED = False

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "analyzer",
        "models_loaded": MODELS_LOADED,
        "timestamp": asyncio.get_event_loop().time()
    }

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    """Analyze uploaded video with AI"""
    try:
        if not MODELS_LOADED:
            raise ModelNotLoadedError()
        
        file_path = await save_uploaded_file(file)
        result = await analyze_video_with_ai(file_path)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/analyze-path")
async def analyze_video_path(request: VideoPathRequest):
    """Analyze video from file path"""
    try:
        if not MODELS_LOADED:
            raise ModelNotLoadedError()
        
        result = await analyze_video_with_ai(request.file)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/scenes")
async def get_scenes(request: ScenesRequest):
    """Get scenes from video file"""
    try:
        result = await analyze_video_file(request.file)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/separate-path")
async def separate_video_audio(request: VideoPathRequest):
    """Separate video and audio from file"""
    try:
        result = await separate_video_audio_handler(request.file)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/cutdown-path")
async def cutdown_video(request: CutdownRequest):
    """Cut video clip from file"""
    try:
        import os
        from handlers.cutdown_handler import time_string_to_seconds
        
        start_time = time_string_to_seconds(request.start)
        end_time = time_string_to_seconds(request.end)
        
        output_filename = request.output_filename or f"cutdown_{request.file.split('/')[-1]}"
        output_path = f"{OUTPUT_DIR}/{output_filename}"
        
        cut_clip(request.file, output_path, start_time, end_time)
        
        # Check if cutdown was successful
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            from utils.error_handler import VideoProcessingError
            raise VideoProcessingError("Cutdown failed - output file is empty or missing")
        
        return JSONResponse(content={
            "output_url": output_path.replace('/app/videos/', '/videos/')
        })
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/generate-cutdown")
async def generate_cutdown(request: CompilationRequest):
    """Generate cutdown from compilation request"""
    try:
        request_data = {
            "selected_scenes": [scene.dict() for scene in request.selected_scenes],
            "audio_file": request.audio_file,
            "original_video": request.original_video
        }
        result = await generate_cutdown_v2(request_data)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/generate-cutdown-v2")
async def generate_cutdown_v2_endpoint(request: CutdownV2Request):
    """Generate cutdown from selected scenes (v2)"""
    try:
        request_data = {
            "selected_scenes": [scene.dict() for scene in request.selected_scenes],
            "audio_file": request.audio_file,
            "original_video": request.original_video
        }
        result = await generate_cutdown_v2(request_data)
        return JSONResponse(content=result)
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

@app.post("/transcribe-path")
async def transcribe_audio_path(request: TranscribeRequest):
    """Transcribe audio from file path"""
    try:
        import requests
        import os
        
        # Forward to whisper service
        whisper_url = "http://whisper:9000/asr"
        
        # Convert /videos/ path to /app/videos/ path
        file_path = request.file.replace('/videos/', '/app/videos/')
        
        # Check if file exists before processing
        if not os.path.exists(file_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"Audio file not found: {request.file}"}
            )
        
        with open(file_path, 'rb') as audio_file:
            files = {'audio_file': audio_file}
            data = {'language_code': request.language} if request.language else {}
            
            response = requests.post(whisper_url, files=files, data=data)
            response.raise_for_status()
            
            return JSONResponse(content=response.json())
    except Exception as e:
        http_exception = handle_exception(e)
        raise http_exception

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
