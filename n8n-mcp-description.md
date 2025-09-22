# Video Analysis Agent - n8n MCP Node Description

## Function Overview
This video analysis system provides AI-powered video processing through two microservices: an Analyzer service (port 8000) and a Whisper service (port 9000). The system processes videos through scene detection, visual analysis, and audio transcription.

## Available Functions

### 1. POST /separate (Analyzer Service)
**Purpose**: Separates video file into video-only and audio-only streams
**Input**: Multipart form with video file
**Output**:
```json
{
  "video_id": "uuid-string",
  "filename": "original_filename.mp4",
  "video_url": "/separated/filename_video.mp4",
  "audio_url": "/separated/filename_audio.mp3"
}
```
**Usage**: Always use this first to prepare video and audio for parallel processing

### 2. POST /asr (Whisper Service)
**Purpose**: Transcribes audio to text using OpenAI Whisper
**Input**: Multipart form with audio file (MP3, WAV, etc.)
**Output**:
```json
{
  "text": "Complete transcribed text content from the audio file"
}
```
**Usage**: Process the audio file obtained from /separate endpoint

### 3. POST /analyze (Analyzer Service)
**Purpose**: Complete video analysis with scene detection and AI visual analysis
**Input**: Multipart form with video file
**Output**:
```json
{
  "video_id": "uuid-string",
  "filename": "video.mp4",
  "scenes": [
    {
      "scene": 0,
      "start_time": "00:00:00.000",
      "end_time": "00:00:05.123",
      "screenshots": [
        {
          "url": "/videos/screenshots/video/scene_000_frame_000.jpg",
          "timestamp": "0:00:01.500000",
          "frame_number": 45,
          "analysis": {
            "description": "Natural language description of the scene",
            "objects": [
              {
                "class": "person|car|dog|etc",
                "confidence": 0.95,
                "position": [x1, y1, x2, y2]
              }
            ],
            "category": "action|dialogue|landscape|group scene|close-up|general",
            "action": "walking|running|talking|fighting|driving|sitting|standing|unknown",
            "importance_score": 0.75
          }
        }
      ]
    }
  ]
}
```
**Usage**: Process the video file obtained from /separate endpoint

### 4. POST /analyze-screenshot (Analyzer Service)
**Purpose**: Analyze single image with AI models
**Input**: Multipart form with image file
**Output**:
```json
{
  "screenshot_id": "uuid-string",
  "filename": "image.jpg",
  "analysis": {
    "description": "Natural language description",
    "objects": [{"class": "string", "confidence": 0.95, "position": [x1,y1,x2,y2]}],
    "category": "scene category",
    "action": "detected action",
    "importance_score": 0.75
  }
}
```

### 5. POST /cutdown (Analyzer Service)
**Purpose**: Extract video segment between timestamps
**Input**: JSON with video_id, start time, end time
**Output**:
```json
{
  "success": true,
  "output": "videos/cutdowns/video_id_cut.mp4"
}
```

## Recommended Workflow for AI Agents

### Step 1: Video Separation
```
POST /separate
Input: Original video file
Result: Separate video-only and audio-only files
```

### Step 2: Parallel Processing
Execute simultaneously:
```
A) POST /asr (Whisper Service)
   Input: Audio file from Step 1
   Result: Text transcription
   
B) POST /analyze (Analyzer Service)
   Input: Video file from Step 1
   Result: Scene detection + visual analysis
```

### Step 3: Combine Results
Merge transcription text with visual analysis data:
- Map transcription timestamps to scene timestamps
- Combine audio content with visual scene descriptions
- Create comprehensive video understanding

## Technical Details

### Service Endpoints
- **Analyzer Service**: `http://analyzer:8000` (internal) or `http://localhost:8000` (external)
- **Whisper Service**: `http://whisper:9000` (internal) or `http://localhost:9000` (external)

### File Handling
- All uploaded files generate unique IDs
- Temporary files are automatically cleaned up
- Static files served at `/videos/` path
- Screenshots saved in `/videos/screenshots/` structure

### AI Model Outputs
- **Scene Description**: Natural language using BLIP model
- **Object Detection**: YOLO v8 with confidence scores and bounding boxes
- **Scene Categories**: action, dialogue, landscape, group scene, close-up, general
- **Actions**: walking, running, talking, fighting, driving, sitting, standing, unknown
- **Importance Score**: 0.0-1.0 relevance rating for content curation

### Error Handling
- Services return HTTP 500 if AI models not loaded
- File validation prevents unsupported formats
- Graceful cleanup of temporary files on errors

### Performance Considerations
- First model loading takes 30-60 seconds
- Scene detection: ~2-5 seconds per minute of video
- Visual analysis: ~1-3 seconds per frame
- Audio transcription: Real-time to 2x speed depending on model size

## Example Integration Workflow

1. **Trigger**: Video file upload to n8n
2. **Separate**: Call `/separate` endpoint → get video_url and audio_url
3. **Parallel Processing**:
   - Branch A: Call `/asr` with audio_url → get transcription
   - Branch B: Call `/analyze` with video_url → get scenes + visual analysis
4. **Merge**: Combine transcription with scene data for complete analysis
5. **Output**: Unified video analysis with both audio and visual insights

This workflow provides comprehensive video understanding suitable for content analysis, summarization, search indexing, and automated video editing tasks. 