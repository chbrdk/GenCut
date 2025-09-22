# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uuid
import subprocess
from typing import List, Union
import os
from scene_utils import analyze_scenes
from ffmpeg_utils import cut_clip, separate_video_audio
from visual_analysis import visual_analyzer
import asyncio
from pydantic import BaseModel, Field, RootModel
import requests

app = FastAPI()

# Mount the videos directory to serve static files
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

UPLOAD_DIR = "/app/videos/uploads"
OUTPUT_DIR = "/app/videos/cutdowns"
SEPARATED_DIR = "/app/videos/separated"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SEPARATED_DIR, exist_ok=True)

# Flag to track if models are loaded
models_loaded = False

class VideoPathRequest(BaseModel):
    file: str

class TranscribeRequest(BaseModel):
    file: str
    language: str = Field(None, alias="language", description="Optional language hint (e.g. 'de', 'en')")

class CutdownRequest(BaseModel):
    file: str
    start: Union[float, str]
    end: Union[float, str]
    output_filename: str = None  # Optional, falls nicht angegeben wird ein Default-Name generiert

class ScenesRequest(BaseModel):
    file: str

# New models for compilation endpoint
class SelectedScene(BaseModel):
    video_url: str
    start_time: str
    end_time: str
    duration: str = None
    screenshot_url: str = None
    description: str = None

class CompilationRequest(BaseModel):
    selected_scenes: List[SelectedScene]
    audio_url: str = None  # Optional audio URL
    original_video: str = None  # Path to original video file

# New model for nested structure
class NestedCompilationRequest(BaseModel):
    selected_scenes: dict  # This will contain the nested structure
    audio_file: str = None  # Optional audio URL (different field name)

@app.on_event("startup")
async def startup_event():
    global models_loaded
    try:
        # Initialize the visual analyzer (this will load the models)
        await visual_analyzer.initialize()
        models_loaded = True
        print("AI models loaded successfully!")
    except Exception as e:
        print(f"Error loading AI models: {e}")
        # Don't set models_loaded to True if there was an error

# Path helpers
def normalize_video_path(input_path: str) -> str:
    """Normalize incoming paths/URLs to an absolute container path under /app/videos/uploads.

    Handles:
    - /app/uploads/<file>  -> /app/videos/uploads/<file>
    - /videos/uploads/<file> -> /app/videos/uploads/<file>
    - absolute /app/videos/uploads/<file> (returns as-is)
    - otherwise returns input_path unchanged
    """
    try:
        if not input_path:
            return input_path
        if input_path.startswith("/app/videos/uploads/"):
            return input_path
        if input_path.startswith("/app/uploads/"):
            return os.path.join(UPLOAD_DIR, os.path.basename(input_path))
        if input_path.startswith("/videos/uploads/"):
            return os.path.join(UPLOAD_DIR, os.path.basename(input_path))
        # URLs or other forms: if it contains '/videos/uploads/', take basename
        if "/videos/uploads/" in input_path or "/uploads/" in input_path:
            return os.path.join(UPLOAD_DIR, os.path.basename(input_path))
        return input_path
    except Exception:
        return input_path

def wait_for_file(path: str, timeout_seconds: float = 20.0, interval: float = 0.5) -> bool:
    """Wait for a file to appear up to timeout. Returns True if exists at end."""
    import time
    end = time.time() + timeout_seconds
    while time.time() < end:
        if os.path.exists(path):
            return True
        time.sleep(interval)
    return os.path.exists(path)

# Helper: ensure a video file exists locally, attempt fetch from nginx if missing
def ensure_local_video_file(path_or_basename: str) -> str:
    """Return a local absolute path under /app/videos/uploads and ensure it exists.

    If the input is an absolute path, take its basename. If the file doesn't exist locally,
    try to download it from nginx static route, then from gencut-frontend.
    """
    try:
        basename = os.path.basename(path_or_basename)
        local_path = os.path.join(UPLOAD_DIR, basename)
        if os.path.exists(local_path):
            return local_path
        # Try nginx first
        try:
            url = f"http://nginx:5679/videos/uploads/{basename}"
            resp = requests.get(url, stream=True, timeout=30)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    return local_path
        except Exception:
            pass
        # Fallback to gencut-frontend
        try:
            url2 = f"http://gencut-frontend:5679/videos/uploads/{basename}"
            resp2 = requests.get(url2, stream=True, timeout=30)
            if resp2.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp2.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    return local_path
        except Exception:
            pass
        return local_path
    except Exception:
        return os.path.join(UPLOAD_DIR, os.path.basename(path_or_basename))

async def _analyze_video_from_path(video_path: str, filename: str, threshold: float | None = None, min_scene_len: int | None = None):
    """Internal function to analyze a video file from a path"""
    if not models_loaded:
        raise HTTPException(status_code=500, detail="AI models not loaded yet")

    # Analyze scenes
    scenes = analyze_scenes(video_path, threshold=threshold, min_scene_len=min_scene_len)
    print(f"analyze_scenes returned {len(scenes)} scenes.")
    # The AI analysis part has been removed as per user request to ensure speed.
    # The service will now only detect scenes and generate screenshots.
    
    return {
        "filename": filename,
        "scenes": scenes
    }

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    """Analyze a video file and return scene information with visual analysis"""
    # Save uploaded file
    video_id = str(uuid.uuid4())
    video_path = os.path.join(UPLOAD_DIR, f"{video_id}_{file.filename}")
    
    with open(video_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    try:
        result = await _analyze_video_from_path(video_path, file.filename)
        result["video_id"] = video_id
        return result
    finally:
        # Clean up the uploaded file
        if os.path.exists(video_path):
            os.remove(video_path)

@app.post("/analyze-path")
async def analyze_video_from_path(request: VideoPathRequest, request_obj: Request = None):
    # Prepend /app/videos/uploads so that the analyzer (which is running in its own container) can find the file.
    video_path = normalize_video_path(request.file)
    if not os.path.exists(video_path):
         # Wait briefly for volume propagation
         if not wait_for_file(video_path):
             # Attempt to ensure the file exists locally by fetching from nginx/frontend
             video_path = ensure_local_video_file(video_path)
    if not os.path.exists(video_path):
         raise HTTPException(status_code=404, detail=f"Video file not found at path: {video_path}")
    filename = os.path.basename(video_path)
    # Read optional sensitivity from query or headers
    thr = None
    min_len = None
    try:
        if request_obj is not None:
            q = request_obj.query_params
            if 'threshold' in q:
                thr = float(q.get('threshold'))
            if 'min_scene_len' in q:
                min_len = int(q.get('min_scene_len'))
    except Exception:
        thr = thr
        min_len = min_len

    return await _analyze_video_from_path(video_path, filename, threshold=thr, min_scene_len=min_len)

@app.post("/cutdown")
def cutdown(video_id: str, start: str, end: str):
    input_path = f"videos/uploads/{video_id}"
    output_path = f"videos/cutdowns/{video_id}_cut.mp4"
    
    success = cut_clip(input_path, output_path, start, end)
    return {"success": success, "output": output_path if success else None}

@app.post("/analyze-screenshot")
async def analyze_single_screenshot(file: UploadFile = File(...)):
    """Analyze a single screenshot image"""
    if not models_loaded:
        raise HTTPException(status_code=500, detail="AI models not loaded yet")

    # Save uploaded file
    screenshot_id = str(uuid.uuid4())
    screenshot_path = os.path.join(UPLOAD_DIR, f"{screenshot_id}_{file.filename}")
    
    try:
        with open(screenshot_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Analyze the screenshot and await the result
        analysis_result = await visual_analyzer.analyze_image(screenshot_path)
        
        return {
            "screenshot_id": screenshot_id,
            "filename": file.filename,
            "analysis": analysis_result
        }
    except Exception as e:
        print(f"Error analyzing screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary file
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

@app.post("/separate-path")
async def separate_video_from_file(request: VideoPathRequest):
    """Separate a video file (given by its path) into video and audio components"""
    # Prepend /app/videos/uploads so that the analyzer (running in its own container) can find the file.
    video_path = normalize_video_path(request.file)
    if not os.path.exists(video_path):
         if not wait_for_file(video_path):
             video_path = ensure_local_video_file(video_path)
    if not os.path.exists(video_path):
         raise HTTPException(status_code=404, detail=f"Video file not found at path: {video_path}")
    filename = os.path.basename(video_path)
    try:
         result = separate_video_audio(video_path, SEPARATED_DIR)
         if not result:
             raise HTTPException(status_code=500, detail="Failed to separate video and audio")
         # Convert paths to URLs (wie bisher)
         video_url = result["video_path"].replace("/app/videos", "")
         response = { "filename": filename, "video_url": video_url }
         if ("audio_path" in result) and (result["audio_path"] is not None):
             audio_url = result["audio_path"].replace("/app/videos", "")
             response["audio_url"] = audio_url
         return response
    except Exception as e:
         print(f"Error separating video: {e}")
         raise HTTPException(status_code=500, detail=str(e))

@app.post("/detect-language-path")
async def detect_language_from_path(file: str = Form(...)):
    if not os.path.exists(file):
        raise HTTPException(status_code=404, detail=f"Audio file not found at path: {file}")
    try:
        with open(file, "rb") as f:
            files = {"audio_file": f}
            response = requests.post("http://whisper:9000/asr", files=files)
        response.raise_for_status()
        result = response.json()
        return {
            "language": result.get("language", "unknown"),
            "confidence": 1.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe-path")
async def transcribe_from_path(request: TranscribeRequest):
    """Transcribe an audio file (given by its path) using Whisper. Optionally, a language hint can be provided."""
    audio_path = request.file
    language = request.language
    if audio_path.startswith("/separated/"):
         audio_path = "/app/videos/separated/" + os.path.basename(audio_path)
    if not os.path.exists(audio_path):
         raise HTTPException(status_code=404, detail=f"Audio file not found at path: {audio_path}")
    try:
         with open(audio_path, "rb") as f:
             files = {"audio_file": f}
             data = {}
             if language:
                 data["language_code"] = language
             response = requests.post("http://whisper:9000/asr", files=files, data=data)
         response.raise_for_status()
         print("Whisper response text:", response.text)
         try:
             return response.json()
         except Exception as json_err:
             print(f"Error parsing Whisper response as JSON: {json_err}")
             print("Whisper response text (on error):", response.text)
             # Fallback: Gib den Text als JSON zurück
             return {"text": response.text.strip()}
    except Exception as e:
         print(f"Error transcribing audio: {e}")
         print("Whisper response text (on error):", getattr(locals().get('response', None), "text", "NO RESPONSE"))
         raise HTTPException(status_code=500, detail=str(e))

@app.post("/cutdown-path")
async def cutdown_from_path(request: Request):
    data = await request.json()
    video_path = data.get("file")
    start = data.get("start")
    end = data.get("end")
    output_filename = data.get("output_filename")

    # Fallback: Akzeptiere sowohl float als auch Zeitstring für start und end
    def parse_time(val):
        if isinstance(val, (float, int)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return time_string_to_seconds(val)
        return 0.0

    start = parse_time(start)
    end = parse_time(end)

    if video_path.startswith("/separated/"):
        video_path = "/app/videos/separated/" + os.path.basename(video_path)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at path: {video_path}")
    try:
        output_path = cutdown_video(video_path, start, end, output_filename)
        return {"output_path": output_path}
    except Exception as e:
        print(f"Error cutting down video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scenes-path")
async def scenes_from_path(request: ScenesRequest):
    video_path = request.file
    if video_path.startswith("/separated/"):
         video_path = "/app/videos/separated/" + os.path.basename(video_path)
    else:
         video_path = normalize_video_path(video_path)
    if not os.path.exists(video_path):
         if not wait_for_file(video_path):
             video_path = ensure_local_video_file(video_path)
    if not os.path.exists(video_path):
         raise HTTPException(status_code=404, detail=f"Video file not found at path: {video_path}")
    try:
         scenes = analyze_scenes(video_path)
         return {"scenes": scenes}
    except Exception as e:
         print(f"Error finding scenes: {e}")
         raise HTTPException(status_code=500, detail=str(e))


# Endpoint to generate a compilation/cutdown from selected scenes
@app.post("/generate-cutdown")
async def generate_cutdown(request: CompilationRequest):
    print(f"Received generate-cutdown request with {len(request.selected_scenes)} scenes")
    print(f"Audio URL: {request.audio_url}")
    print(f"Original video: {request.original_video}")
    
    # Process each selected scene by cutting it from the original video
    scene_files = []
    
    # Use original video path if provided, otherwise fall back to separated video
    base_video_path = None
    if request.original_video:
        base_video_path = request.original_video
        if not os.path.exists(base_video_path):
            raise HTTPException(status_code=404, detail=f"Original video file not found at path: {base_video_path}")
        print(f"Using original video: {base_video_path}")
    else:
        # Fallback to separated video (old behavior)
        if request.selected_scenes and len(request.selected_scenes) > 0:
            video_path = request.selected_scenes[0].video_url
            if video_path.startswith("/separated/"):
                base_video_path = "/app/videos/separated/" + os.path.basename(video_path)
            elif video_path.startswith("/videos/uploads/"):
                base_video_path = "/app/videos/uploads/" + os.path.basename(video_path)
            
            if not os.path.exists(base_video_path):
                raise HTTPException(status_code=404, detail=f"Video file not found at path: {base_video_path}")
            print(f"Using separated video: {base_video_path}")
    
    for i, scene in enumerate(request.selected_scenes):
        print(f"Processing scene {i}: {scene.start_time} - {scene.end_time}")
        
        # Convert time strings to seconds for ffmpeg
        start_seconds = time_string_to_seconds(scene.start_time)
        end_seconds = time_string_to_seconds(scene.end_time)
        
        print(f"Scene {i} time range: {start_seconds}s - {end_seconds}s (duration: {end_seconds - start_seconds}s)")
        
        # Generate output filename for this scene
        scene_filename = f"{uuid.uuid4()}_scene_{i:03d}.mp4"
        scene_output_path = os.path.join(OUTPUT_DIR, scene_filename)
        
        # Cut the scene from the original video
        success = cut_clip(base_video_path, scene_output_path, start_seconds, end_seconds)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to cut scene {i}")
        
        scene_files.append(scene_output_path)

    print(f"Successfully cut {len(scene_files)} scenes")

    # Create FFmpeg concat list file
    list_file = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_concat_list.txt")
    with open(list_file, "w") as f:
        for p in scene_files:
            f.write(f"file '{p}'\n")
    
    print(f"Created concat list file: {list_file}")
    print(f"Scene files to concatenate:")
    for i, scene_file in enumerate(scene_files):
        if os.path.exists(scene_file):
            file_size = os.path.getsize(scene_file)
            print(f"  Scene {i}: {scene_file} ({file_size} bytes)")
        else:
            print(f"  Scene {i}: {scene_file} (MISSING!)")

    # Generate unique output filename
    output_filename = f"{uuid.uuid4()}_cutdown.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    try:
        # First concatenate video clips without audio
        temp_video = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_temp.mp4")
        # Entferne Audio beim Zusammenfügen der Clips
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "copy",  # Kopiere Video-Stream
            "-an",          # Entferne Audio
            temp_video
        ]
        print(f"Running FFmpeg concat command: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        print(f"FFmpeg concat stdout: {process.stdout}")
        print(f"FFmpeg concat stderr: {process.stderr}")
        print(f"FFmpeg concat return code: {process.returncode}")
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg concat failed: {process.stderr}")
        
        # Check if temp video was created
        if os.path.exists(temp_video):
            temp_size = os.path.getsize(temp_video)
            print(f"Temp video created successfully: {temp_video} ({temp_size} bytes)")
        else:
            print(f"ERROR: Temp video not created: {temp_video}")
            raise HTTPException(status_code=500, detail="Temp video not created")

        # If audio URL is provided, download and combine with video
        if request.audio_url:
            try:
                print(f"Downloading audio from: {request.audio_url}")
                # Download audio file
                audio_response = requests.get(request.audio_url)
                audio_response.raise_for_status()
                audio_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_audio.mp3")
                with open(audio_path, 'wb') as f:
                    f.write(audio_response.content)

                # Combine video (without original audio) and new audio
                cmd = [
                    "ffmpeg", "-i", temp_video,  # Video ohne Audio
                    "-i", audio_path,            # Neuer Audio-Track
                    "-c:v", "copy",              # Kopiere Video-Stream
                    "-c:a", "aac",               # Konvertiere Audio zu AAC
                    "-map", "0:v:0",             # Verwende Video vom ersten Input
                    "-map", "1:a:0",             # Verwende Audio vom zweiten Input
                    "-shortest",                 # Beende wenn kürzester Stream endet
                    output_path
                ]
                process = subprocess.run(cmd, capture_output=True, text=True)
                if process.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"FFmpeg audio merge failed: {process.stderr}")

                # Clean up temporary audio file
                os.remove(audio_path)
            except requests.exceptions.RequestException as e:
                raise HTTPException(status_code=500, detail=f"Failed to download audio: {str(e)}")
            finally:
                # Clean up temporary video file
                if os.path.exists(temp_video):
                    os.remove(temp_video)
        else:
            # If no audio URL provided, just move the temp video (which has no audio) to output
            os.rename(temp_video, output_path)

        # Clean up concat list file and individual scene files
        os.remove(list_file)
        for scene_file in scene_files:
            if os.path.exists(scene_file):
                os.remove(scene_file)

        print(f"Cutdown completed successfully: {output_filename}")

        # Return the public URL of the generated video
        return JSONResponse(content={
            "output_url": f"/videos/cutdowns/{output_filename}"
        })

    except Exception as e:
        # Clean up any temporary files in case of error
        for path in [list_file, temp_video, output_path] + scene_files:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to generate a compilation/cutdown from selected scenes (supports both formats)
@app.post("/generate-cutdown-v2")
async def generate_cutdown_v2(request: dict):
    """
    Generate cutdown from selected scenes. Supports both flat and nested formats:
    - Flat: {"selected_scenes": [...], "audio_url": "...", "original_video": "..."}
    - Nested: {"selected_scenes": {"selected_scenes": [...], "music_prompt": "..."}, "audio_file": "...", "original_video": "..."}
    """
    print(f"Received request: {request}")
    
    # Extract scenes and audio URL based on format
    selected_scenes = []
    audio_url = None
    original_video = None
    
    if "selected_scenes" in request:
        if isinstance(request["selected_scenes"], list):
            # Flat format
            selected_scenes = request["selected_scenes"]
            audio_url = request.get("audio_url")
            original_video = request.get("original_video")
        elif isinstance(request["selected_scenes"], dict) and "selected_scenes" in request["selected_scenes"]:
            # Nested format
            selected_scenes = request["selected_scenes"]["selected_scenes"]
            audio_url = request.get("audio_file")  # Different field name in nested format
            original_video = request.get("original_video")
        else:
            raise HTTPException(status_code=400, detail="Invalid selected_scenes format")
    
    if not selected_scenes:
        raise HTTPException(status_code=400, detail="No selected scenes provided")
    
    print(f"Processing {len(selected_scenes)} scenes")
    print(f"Audio URL: {audio_url}")
    print(f"Original video: {original_video}")
    
    # Process each selected scene by cutting it from the original video
    scene_files = []
    
    # Use original video path if provided, otherwise fall back to separated video
    base_video_path = None
    if original_video:
        base_video_path = original_video
        if not os.path.exists(base_video_path):
            raise HTTPException(status_code=404, detail=f"Original video file not found at path: {base_video_path}")
        print(f"Using original video: {base_video_path}")
    else:
        # Fallback to separated video (old behavior)
        if selected_scenes and len(selected_scenes) > 0:
            video_path = selected_scenes[0].get("video_url")
            if video_path:
                if video_path.startswith("/separated/"):
                    base_video_path = "/app/videos/separated/" + os.path.basename(video_path)
                elif video_path.startswith("/videos/uploads/"):
                    base_video_path = "/app/videos/uploads/" + os.path.basename(video_path)
                
                if not os.path.exists(base_video_path):
                    raise HTTPException(status_code=404, detail=f"Video file not found at path: {base_video_path}")
                print(f"Using separated video: {base_video_path}")
    
    for i, scene in enumerate(selected_scenes):
        # Convert time strings to seconds for ffmpeg
        start_time = scene.get("start_time")
        end_time = scene.get("end_time")
        if not start_time or not end_time:
            raise HTTPException(status_code=400, detail=f"Scene {i} missing start_time or end_time")
            
        start_seconds = time_string_to_seconds(start_time)
        end_seconds = time_string_to_seconds(end_time)
        
        print(f"Cutting scene {i}: {start_time} - {end_time} ({start_seconds}s - {end_seconds}s)")
        
        # Generate output filename for this scene
        scene_filename = f"{uuid.uuid4()}_scene_{i:03d}.mp4"
        scene_output_path = os.path.join(OUTPUT_DIR, scene_filename)
        
        print(f"Scene {i} output path: {scene_output_path}")
        print(f"Scene {i} video path: {base_video_path}")
        print(f"Scene {i} time range: {start_seconds}s - {end_seconds}s (duration: {end_seconds - start_seconds}s)")
        
        # Cut the scene from the original video
        success = cut_clip(base_video_path, scene_output_path, start_seconds, end_seconds)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to cut scene {i}")
        
        # Check if the scene file was created and has content
        if os.path.exists(scene_output_path):
            file_size = os.path.getsize(scene_output_path)
            print(f"Scene {i} created successfully: {scene_output_path} ({file_size} bytes)")
        else:
            print(f"ERROR: Scene {i} file not created: {scene_output_path}")
            raise HTTPException(status_code=500, detail=f"Scene {i} file not created")
        
        scene_files.append(scene_output_path)

    # Create FFmpeg concat list file
    list_file = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_concat_list.txt")
    with open(list_file, "w") as f:
        for p in scene_files:
            f.write(f"file '{p}'\n")
    
    print(f"Created concat list file: {list_file}")
    print(f"Scene files to concatenate:")
    for i, scene_file in enumerate(scene_files):
        if os.path.exists(scene_file):
            file_size = os.path.getsize(scene_file)
            print(f"  Scene {i}: {scene_file} ({file_size} bytes)")
        else:
            print(f"  Scene {i}: {scene_file} (MISSING!)")

    # Generate unique output filename
    output_filename = f"{uuid.uuid4()}_cutdown.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    try:
        # First concatenate video clips without audio
        temp_video = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_temp.mp4")
        # Entferne Audio beim Zusammenfügen der Clips
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "copy",  # Kopiere Video-Stream
            "-an",          # Entferne Audio
            temp_video
        ]
        print(f"Running FFmpeg concat command: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        print(f"FFmpeg concat stdout: {process.stdout}")
        print(f"FFmpeg concat stderr: {process.stderr}")
        print(f"FFmpeg concat return code: {process.returncode}")
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg concat failed: {process.stderr}")
        
        # Check if temp video was created
        if os.path.exists(temp_video):
            temp_size = os.path.getsize(temp_video)
            print(f"Temp video created successfully: {temp_video} ({temp_size} bytes)")
        else:
            print(f"ERROR: Temp video not created: {temp_video}")
            raise HTTPException(status_code=500, detail="Temp video not created")

        # If audio URL is provided, download and combine with video
        if audio_url:
            try:
                print(f"Downloading audio from: {audio_url}")
                # Download audio file
                audio_response = requests.get(audio_url)
                audio_response.raise_for_status()
                audio_path = os.path.join(OUTPUT_DIR, f"{uuid.uuid4()}_audio.mp3")
                with open(audio_path, 'wb') as f:
                    f.write(audio_response.content)

                # Combine video (without original audio) and new audio
                cmd = [
                    "ffmpeg", "-i", temp_video,  # Video ohne Audio
                    "-i", audio_path,            # Neuer Audio-Track
                    "-c:v", "copy",              # Kopiere Video-Stream
                    "-c:a", "aac",               # Konvertiere Audio zu AAC
                    "-map", "0:v:0",             # Verwende Video vom ersten Input
                    "-map", "1:a:0",             # Verwende Audio vom zweiten Input
                    "-shortest",                 # Beende wenn kürzester Stream endet
                    output_path
                ]
                process = subprocess.run(cmd, capture_output=True, text=True)
                if process.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"FFmpeg audio merge failed: {process.stderr}")

                # Clean up temporary audio file
                os.remove(audio_path)
            except requests.exceptions.RequestException as e:
                raise HTTPException(status_code=500, detail=f"Failed to download audio: {str(e)}")
            finally:
                # Clean up temporary video file
                if os.path.exists(temp_video):
                    os.remove(temp_video)
        else:
            # If no audio URL provided, just move the temp video (which has no audio) to output
            os.rename(temp_video, output_path)

        # Clean up concat list file and individual scene files
        os.remove(list_file)
        for scene_file in scene_files:
            if os.path.exists(scene_file):
                os.remove(scene_file)

        # Return the public URL of the generated video
        return JSONResponse(content={
            "output_url": f"/videos/cutdowns/{output_filename}"
        })

    except Exception as e:
        # Clean up any temporary files in case of error
        for path in [list_file, temp_video, output_path] + scene_files:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=str(e))

def cutdown_video(video_path: str, start: float, end: float, output_filename: str = None) -> str:
    """Cut a video clip from start to end time (in seconds)"""
    try:
        if output_filename:
            # Wenn ein benutzerdefinierter Dateiname angegeben wurde, verwende diesen
            output_path = os.path.join(OUTPUT_DIR, output_filename)
        else:
            # Sonst generiere einen Default-Namen
            video_filename = os.path.basename(video_path)
            base_name = os.path.splitext(video_filename)[0]
            output_path = os.path.join(OUTPUT_DIR, f"{base_name}_cut.mp4")
        
        # Cut the clip
        success = cut_clip(video_path, output_path, start, end)
        if not success:
            raise Exception("Failed to cut video clip")
            
        return output_path
    except Exception as e:
        print(f"Error in cutdown_video: {e}")
        raise

@app.post("/asr-path")
async def transcribe_audio_from_path(file: str = Form(...)):
    if not os.path.exists(file):
        raise HTTPException(status_code=404, detail=f"Audio file not found at path: {file}")
    try:
        with open(file, "rb") as f:
            files = {"audio_file": f}
            response = requests.post("http://whisper:9000/asr", files=files)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def time_string_to_seconds(time_str: str) -> float:
    """Convert time string (HH:MM:SS.mmmmmm) to seconds"""
    try:
        # Handle different time formats
        if '.' in time_str:
            time_part, ms_part = time_str.split('.')
            ms_part = ms_part.ljust(6, '0')  # Ensure 6 digits
            ms = float(ms_part) / 1000000
        else:
            time_part = time_str
            ms = 0.0
        
        # Parse HH:MM:SS
        parts = time_part.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            total_seconds = hours * 3600 + minutes * 60 + seconds + ms
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            total_seconds = minutes * 60 + seconds + ms
        else:
            total_seconds = float(time_str)
        
        return total_seconds
    except Exception as e:
        print(f"Error parsing time string '{time_str}': {e}")
        return 0.0
