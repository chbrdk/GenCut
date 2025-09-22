# handlers/cutdown_handler.py
import os
import uuid
import subprocess
import requests
from typing import List, Dict, Any
from ..utils.error_handler import VideoProcessingError, FileNotFoundError
from ..config import OUTPUT_DIR, SEPARATED_DIR
from ..ffmpeg_utils import cut_clip, separate_video_audio
from ..models.requests import SelectedScene

def time_string_to_seconds(time_str: str) -> float:
    """Convert time string (HH:MM:SS.mmmmmm) to seconds"""
    if isinstance(time_str, (int, float)):
        return float(time_str)
    
    parts = time_str.split(':')
    if len(parts) == 3:  # HH:MM:SS.mmmmmm
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:  # MM:SS
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        return float(time_str)

def normalize_video_path(input_path: str) -> str:
    """Normalize video path for processing"""
    if input_path.startswith('/videos/'):
        return input_path.replace('/videos/', '/app/videos/')
    return input_path

async def generate_cutdown_v2(request_data: Dict[str, Any]) -> Dict[str, str]:
    """Generate cutdown from selected scenes"""
    try:
        selected_scenes = request_data.get('selected_scenes', [])
        audio_file = request_data.get('audio_file')
        original_video = request_data.get('original_video')
        
        if not selected_scenes:
            raise VideoProcessingError("No scenes selected for cutdown")
        
        # Determine base video path
        base_video = None
        if original_video:
            base_video = normalize_video_path(original_video)
        elif selected_scenes:
            first_scene_path = normalize_video_path(selected_scenes[0]['video_url'])
            if os.path.exists(first_scene_path):
                base_video = first_scene_path
        
        if not base_video or not os.path.exists(base_video):
            raise FileNotFoundError(base_video or "base video")
        
        # Cut individual scenes
        scene_files = []
        for i, scene in enumerate(selected_scenes):
            start_time = time_string_to_seconds(scene['start_time'])
            end_time = time_string_to_seconds(scene['end_time'])
            duration = end_time - start_time
            
            scene_filename = f"scene_{i:03d}_{uuid.uuid4().hex[:8]}.mp4"
            scene_path = os.path.join(OUTPUT_DIR, scene_filename)
            
            cut_clip(base_video, scene_path, start_time, duration)
            scene_files.append(scene_path)
        
        # Concatenate scenes
        final_filename = f"cutdown_{uuid.uuid4().hex[:8]}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_filename)
        
        # Create concat file
        concat_file = os.path.join(OUTPUT_DIR, f"concat_{uuid.uuid4().hex[:8]}.txt")
        with open(concat_file, 'w') as f:
            for scene_file in scene_files:
                f.write(f"file '{scene_file}'\n")
        
        # Concatenate using ffmpeg
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy", "-y", final_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise VideoProcessingError(f"FFmpeg concatenation failed: {result.stderr}")
        
        # Add audio if provided
        if audio_file:
            audio_path = os.path.join(OUTPUT_DIR, f"audio_{uuid.uuid4().hex[:8]}.mp3")
            
            # Download audio file
            if audio_file.startswith('http'):
                response = requests.get(audio_file)
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
            else:
                audio_path = normalize_video_path(audio_file)
            
            # Merge video and audio
            final_with_audio = os.path.join(OUTPUT_DIR, f"final_{uuid.uuid4().hex[:8]}.mp4")
            cmd = [
                "ffmpeg", "-i", final_path, "-i", audio_path,
                "-c:v", "copy", "-c:a", "aac", "-shortest", "-y", final_with_audio
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                final_path = final_with_audio
        
        # Clean up temporary files
        os.remove(concat_file)
        for scene_file in scene_files:
            if os.path.exists(scene_file):
                os.remove(scene_file)
        
        return {"output_url": final_path.replace('/app/videos/', '/videos/')}
        
    except Exception as e:
        raise VideoProcessingError(f"Failed to generate cutdown: {str(e)}")

async def separate_video_audio_handler(file_path: str) -> Dict[str, str]:
    """Separate video and audio from file"""
    try:
        normalized_path = normalize_video_path(file_path)
        if not os.path.exists(normalized_path):
            raise FileNotFoundError(normalized_path)
        
        filename = os.path.basename(normalized_path).split('.')[0]
        video_output = os.path.join(SEPARATED_DIR, f"{filename}_video.mp4")
        audio_output = os.path.join(SEPARATED_DIR, f"{filename}_audio.mp3")
        
        separate_video_audio(normalized_path, SEPARATED_DIR)
        
        return {
            "filename": os.path.basename(normalized_path),
            "video_url": video_output.replace('/app/videos/', '/videos/'),
            "audio_url": audio_output.replace('/app/videos/', '/videos/')
        }
    except Exception as e:
        raise VideoProcessingError(f"Failed to separate video/audio: {str(e)}")
