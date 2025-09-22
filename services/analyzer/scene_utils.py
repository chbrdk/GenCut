# analyzer/scene_utils.py
import cv2
import os
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from datetime import timedelta

def resize_frame(frame, target_width=640):
    """Resize frame maintaining aspect ratio"""
    height = int(frame.shape[0] * (target_width / frame.shape[1]))
    return cv2.resize(frame, (target_width, height), interpolation=cv2.INTER_AREA)

def analyze_scenes(video_path: str, threshold: float | None = None, min_scene_len: int | None = None):
    # Create screenshots directory if it doesn't exist
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # Fix: Always save screenshots to /app/videos/screenshots/ regardless of video location
    base_videos_dir = "/app/videos"
    screenshots_dir = os.path.join(base_videos_dir, 'screenshots', video_name)
    os.makedirs(screenshots_dir, exist_ok=True)

    # Open video for both scene detection and frame capture
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    # Allow tuning sensitivity via parameters or environment variables
    env_threshold = float(os.getenv('SCENE_THRESHOLD', '18'))
    env_min_len = int(os.getenv('SCENE_MIN_LEN', '8'))
    detector_threshold = float(threshold) if threshold is not None else env_threshold
    detector_min_len = int(min_scene_len) if min_scene_len is not None else env_min_len
    scene_manager.add_detector(ContentDetector(threshold=detector_threshold, min_scene_len=detector_min_len))

    # Open video for frame capture
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * 1.0)  # Capture every ~1.0 seconds for denser sampling

    video_manager.set_downscale_factor()
    video_manager.start()

    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()

    result = []
    for i, (start, end) in enumerate(scene_list):
        # Calculate frame numbers for screenshots
        start_frame = int(start.get_frames())
        end_frame = int(end.get_frames())
        
        # OPTIMIZATION: To prevent timeouts, we now only analyze one representative
        # screenshot from the middle of each scene.
        frame_numbers = [start_frame + (end_frame - start_frame) // 2]
        if not frame_numbers: # Ensure at least one frame is processed for very short scenes
            frame_numbers = [start_frame]
        
        scene_screenshots = []
        for frame_idx, frame_number in enumerate(frame_numbers):
            # Set video position to the frame we want
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if ret:
                # Resize frame
                frame = resize_frame(frame)
                
                # Save screenshot with compression
                screenshot_path = os.path.join(screenshots_dir, f'scene_{i:03d}_frame_{frame_idx:03d}.jpg')
                cv2.imwrite(screenshot_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                # Calculate timestamp for this frame
                timestamp = start.get_seconds() + (frame_number - start_frame) / fps
                time_str = str(timedelta(seconds=timestamp))
                
                screenshot_url = f'/videos/screenshots/{video_name}/scene_{i:03d}_frame_{frame_idx:03d}.jpg'
                scene_screenshots.append({
                    "url": screenshot_url,
                    "path": screenshot_path,
                    "timestamp": time_str,
                    "frame_number": frame_number
                })

        result.append({
            "scene": i,
            "start_time": start.get_timecode(),
            "end_time": end.get_timecode(),
            "screenshots": scene_screenshots
        })
    
    # Cleanup
    video_manager.release()
    cap.release()
    return result
