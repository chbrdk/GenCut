# Video Analysis Agent

A comprehensive video analysis system that combines computer vision, scene detection, and audio transcription capabilities. The project consists of two microservices deployed with Docker Compose: an analyzer service for visual processing and a Whisper service for speech recognition.

## 🎯 Overview

This system provides advanced video analysis capabilities including:
- **Scene Detection**: Automatic detection and segmentation of video scenes
- **Visual Analysis**: AI-powered image analysis using BLIP and YOLO models
- **Audio Transcription**: Speech-to-text using OpenAI Whisper
- **Video Processing**: Cutting, trimming, and audio separation using FFmpeg
- **REST API**: Complete API for integration with other applications

## 🏗️ Architecture

```
video-analysis-agent/
├── analyzer/           # Main analysis service
│   ├── main.py        # FastAPI application
│   ├── visual_analysis.py  # Computer vision models
│   ├── scene_utils.py # Scene detection utilities
│   ├── ffmpeg_utils.py # Video processing utilities
│   ├── requirements.txt
│   └── Dockerfile
├── whisper/           # Speech recognition service
│   └── Dockerfile     # Whisper ASR service
├── docker-compose.yml # Service orchestration
└── videos/           # Video storage (mounted volume)
    ├── uploads/      # Uploaded videos
    ├── cutdowns/     # Processed clips
    ├── separated/    # Video/audio separation
    └── screenshots/  # Extracted frames
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- At least 4GB RAM (for AI models)
- CUDA-compatible GPU (optional, for faster processing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd video-analysis-agent
```

2. Start the services:
```bash
docker-compose up -d
```

3. Wait for model initialization (first startup takes longer):
```bash
docker-compose logs -f analyzer
```

### Verify Installation

Check if services are running:
```bash
# Analyzer service
curl http://localhost:8000/docs

# Whisper service  
curl http://localhost:9000/docs
```

## 📡 API Reference

### Analyzer Service (Port 8000)

#### `POST /analyze`
Comprehensive video analysis with scene detection and visual AI.

**Request:**
```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@video.mp4"
```

**Response:**
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
            "description": "a person walking in a park",
            "objects": [
              {
                "class": "person",
                "confidence": 0.95,
                "position": [100, 50, 200, 300]
              }
            ],
            "category": "action",
            "action": "walking", 
            "importance_score": 0.75
          }
        }
      ]
    }
  ]
}
```

#### `POST /analyze-screenshot`
Analyze a single image with AI models.

**Request:**
```bash
curl -X POST "http://localhost:8000/analyze-screenshot" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@image.jpg"
```

#### `POST /cutdown`
Extract a video segment between specified timestamps.

**Request:**
```bash
curl -X POST "http://localhost:8000/cutdown" \
     -H "Content-Type: application/json" \
     -d '{
       "video_id": "filename.mp4",
       "start": "00:00:10",
       "end": "00:00:20"
     }'
```

#### `POST /separate`
Separate video into video-only and audio-only files.

**Request:**
```bash
curl -X POST "http://localhost:8000/separate" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@video.mp4"
```

### Whisper Service (Port 9000)

#### `POST /asr`
Convert audio to text using OpenAI Whisper.

**Request:**
```bash
curl -X POST "http://localhost:9000/asr" \
     -H "Content-Type: multipart/form-data" \
     -F "audio_file=@audio.mp3"
```

**Response:**
```json
{
  "text": "Transcribed speech content..."
}
```

## 🤖 AI Models & Technologies

### Computer Vision Models
- **BLIP (Salesforce/blip-image-captioning-base)**: Scene description generation
- **YOLOv8n**: Real-time object detection
- **PyTorch**: Deep learning framework

### Scene Detection
- **PySceneDetect**: Content-based scene boundary detection
- **OpenCV**: Image processing and frame extraction

### Audio Processing
- **OpenAI Whisper**: State-of-the-art speech recognition
- **FFmpeg**: Video/audio processing and conversion

### Web Framework
- **FastAPI**: High-performance async API framework
- **Uvicorn**: ASGI server

## 🔧 Configuration

### Environment Variables

**Whisper Service:**
- `ASR_MODEL=base` - Whisper model size (tiny, base, small, medium, large)
- `ASR_ENGINE=openai_whisper` - ASR engine type
- `ASR_DEVICE=cpu` - Processing device (cpu/cuda)
- `ASR_COMPUTE_TYPE=int8` - Computation precision
- `ASR_BATCH_SIZE=1` - Batch size for processing

### Volume Mounts
- `./videos:/app/videos` - Persistent video storage
- `whisper_models:/app/asr_models` - Whisper model cache

## 📊 Features Deep Dive

### Scene Analysis
The system automatically:
1. Detects scene boundaries using content-based analysis
2. Extracts representative frames every 1.5 seconds
3. Resizes frames to 640px width for efficiency
4. Saves screenshots with 85% JPEG quality

### Visual Analysis
For each frame, the AI analyzes:
- **Scene Description**: Natural language description of what's happening
- **Object Detection**: Identification and localization of objects/people
- **Scene Categorization**: Classification (action, dialogue, landscape, etc.)
- **Action Recognition**: Detection of activities (walking, talking, fighting, etc.)
- **Importance Scoring**: Relevance score (0-1) for content curation

### Audio Processing
- Extract audio from video files
- Separate video into video-only and audio-only streams
- Transcribe speech with high accuracy
- Support for multiple audio formats

## 🛠️ Development

### Local Development Setup

1. Install Python dependencies:
```bash
cd analyzer
pip install -r requirements.txt
```

2. Run analyzer locally:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

3. Run Whisper service:
```bash
cd whisper
docker build -t whisper-service .
docker run -p 9000:9000 whisper-service
```

### Adding New Analysis Features

1. **Extend Visual Analysis**: Modify `visual_analysis.py` to add new AI models
2. **Add Processing Functions**: Create new utilities in `ffmpeg_utils.py`
3. **New API Endpoints**: Add routes in `main.py`

### Model Customization

Replace AI models by modifying the model initialization in `visual_analysis.py`:
```python
# Use different BLIP model
self.scene_description_model = BlipForConditionalGeneration.from_pretrained("custom-model")

# Use different YOLO model
self.object_detection_model = YOLO('yolov8s.pt')  # Small instead of nano
```

## 🚨 Troubleshooting

### Common Issues

**Models not loading:**
```bash
# Check logs
docker-compose logs analyzer

# Restart with fresh models
docker-compose down -v
docker-compose up -d
```

**Out of memory:**
- Reduce model size (use `yolov8n.pt` instead of larger variants)
- Increase Docker memory allocation
- Use CPU instead of GPU processing

**Video processing fails:**
- Ensure FFmpeg is properly installed
- Check video format compatibility
- Verify sufficient disk space

**Whisper service connection issues:**
```bash
# Test connectivity
docker-compose exec analyzer ping whisper
```

### Performance Optimization

1. **GPU Acceleration**: Set `ASR_DEVICE=cuda` for Whisper
2. **Model Caching**: Models are cached in volumes for faster restarts
3. **Parallel Processing**: Visual analysis runs screenshots in parallel
4. **Frame Optimization**: Frames are resized and compressed for efficiency

## 📈 Performance Metrics

**Typical Processing Times:**
- Scene detection: ~2-5 seconds per minute of video
- Visual analysis: ~1-3 seconds per frame
- Audio transcription: ~Real-time to 2x speed (depending on model)

**Resource Requirements:**
- RAM: 2-8GB (depending on models and video resolution)
- Storage: ~10-50MB per minute of processed video
- CPU: Multi-core recommended for parallel processing

## 🔒 Security Considerations

- File uploads are validated and stored in isolated directories
- Temporary files are automatically cleaned up
- Services run in isolated Docker containers
- No external network access required (models run locally)



## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📞 Support

For issues and questions:
- Check logs: `docker-compose logs`
- Review API documentation: `http://localhost:8000/docs`
- Open GitHub issues for bugs and feature requests
