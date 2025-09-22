# app_new.py - Refactored revoice service with shared libraries
from flask import Flask, request, jsonify, render_template_string
import os
import uuid
import requests
import logging
import time
from werkzeug.utils import secure_filename
from typing import Dict, Any

# Import shared libraries
import sys
sys.path.append('/app/shared')
from elevenlabs_client import get_elevenlabs_client, ElevenLabsError
from utils.error_handler import register_error_handlers, UploadError, FileNotFoundError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = '/app/videos/uploads'
CUTDOWNS_FOLDER = '/app/videos/cutdowns'
SCREENSHOTS_FOLDER = '/app/videos/screenshots'
REVOICED_FOLDER = '/app/videos/revoiced'
SEPARATED_FOLDER = '/app/videos/separated'
TEMP_FOLDER = '/app/temp'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB

# Umgebungsbasierte Konfiguration
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ENV = os.environ.get('FLASK_ENV', 'production')

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    DEBUG=DEBUG,
    ENV=ENV
)

# Register error handlers
register_error_handlers(app)

# Ensure all folders exist
for folder in [UPLOAD_FOLDER, CUTDOWNS_FOLDER, SCREENSHOTS_FOLDER, REVOICED_FOLDER, SEPARATED_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

video_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_video_id():
    return f"revoice_{int(time.time())}_{uuid.uuid4().hex[:8]}"

@app.route('/')
def index():
    """Main upload interface for revoicing"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GenCut - Video Revoicing</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">GenCut Video Revoicing</h1>
        
        <div class="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6">
            <form id="uploadForm" enctype="multipart/form-data" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Video-Datei auswählen</label>
                    <input type="file" name="video" accept="video/*" required 
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                
                <button type="submit" 
                        class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    Video hochladen für Revoicing
                </button>
            </form>
            
            <div id="status" class="mt-4 hidden">
                <div class="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded">
                    <p id="statusText"></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const statusDiv = document.getElementById('status');
            const statusText = document.getElementById('statusText');
            
            statusDiv.classList.remove('hidden');
            statusText.textContent = 'Video wird hochgeladen...';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    statusText.textContent = `Upload erfolgreich! Video-ID: ${result.video_id}`;
                    statusDiv.className = 'mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded';
                } else {
                    statusText.textContent = `Fehler: ${result.error}`;
                    statusDiv.className = 'mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded';
                }
            } catch (error) {
                statusText.textContent = `Fehler: ${error.message}`;
                statusDiv.className = 'mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded';
            }
        });
    </script>
</body>
</html>
    ''')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload video file for revoicing"""
    try:
        if 'video' not in request.files:
            raise UploadError("Keine Video-Datei gefunden")
        
        file = request.files['video']
        if file.filename == '':
            raise UploadError("Keine Datei ausgewählt")
        
        if not allowed_file(file.filename):
            raise UploadError("Dateiformat nicht unterstützt")
        
        # Generate unique filename
        video_id = generate_video_id()
        filename = secure_filename(file.filename)
        unique_filename = f"{video_id}.mp4"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Store session info
        video_sessions[video_id] = {
            'filename': unique_filename,
            'file_path': file_path,
            'status': 'uploaded',
            'timestamp': time.time()
        }
        
        # Send to n8n webhook for lip-sync processing
        webhook_data = {
            'video_id': video_id,
            'filename': unique_filename,
            'file_path': file_path,
            'service': 'revoice'
        }
        
        try:
            webhook_response = requests.post(
                'http://n8n:5678/webhook/lip-sync',
                json=webhook_data,
                timeout=30
            )
            webhook_status = "success" if webhook_response.status_code == 200 else "failed"
        except Exception as e:
            logger.warning(f"Webhook call failed: {e}")
            webhook_status = "failed"
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'filename': unique_filename,
            'status': 'processing',
            'webhook_status': webhook_status
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise UploadError(f"Upload failed: {str(e)}")

@app.route('/status/<video_id>')
def get_status(video_id):
    """Get processing status of video"""
    try:
        if video_id not in video_sessions:
            raise FileNotFoundError(f"Session not found: {video_id}")
        
        session = video_sessions[video_id]
        
        # Check if revoiced file exists
        revoiced_path = os.path.join(REVOICED_FOLDER, f"{video_id}_revoiced.mp4")
        
        if os.path.exists(revoiced_path):
            session['status'] = 'completed'
            session['revoiced_path'] = revoiced_path
            
            return jsonify({
                'status': 'completed',
                'message': 'Revoicing erfolgreich abgeschlossen',
                'revoiced_path': f'/videos/revoiced/{os.path.basename(revoiced_path)}',
                'session': session
            })
        else:
            return jsonify({
                'status': 'processing',
                'message': 'Video wird noch verarbeitet...',
                'session': session
            })
            
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise UploadError(f"Status check failed: {str(e)}")

@app.route('/elevenlabs/voices')
def get_elevenlabs_voices():
    """Get list of available ElevenLabs voices"""
    try:
        client = get_elevenlabs_client()
        voices = client.get_voices()
        return jsonify(voices)
    except Exception as e:
        logger.error(f"ElevenLabs voices error: {e}")
        raise ElevenLabsError(f"Failed to fetch voices: {str(e)}")

@app.route('/elevenlabs/preview', methods=['POST'])
def preview_elevenlabs_voice():
    """Preview ElevenLabs voice"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text', 'Hallo, das ist ein Test.')
        
        if not voice_id:
            raise ElevenLabsError("Voice-ID erforderlich")
        
        client = get_elevenlabs_client()
        audio_data = client.preview_voice(voice_id, text)
        
        return jsonify({
            'success': True,
            'audio_data': audio_data.hex()  # Convert to hex string for JSON
        })
    except Exception as e:
        logger.error(f"ElevenLabs preview error: {e}")
        raise ElevenLabsError(f"Preview failed: {str(e)}")

@app.route('/elevenlabs/generate', methods=['POST'])
def generate_elevenlabs_audio():
    """Generate audio with ElevenLabs"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text')
        model_id = data.get('model_id', 'eleven_multilingual_v2')
        
        if not voice_id or not text:
            raise ElevenLabsError("Voice-ID und Text erforderlich")
        
        client = get_elevenlabs_client()
        audio_data = client.generate_audio(voice_id, text, model_id)
        
        return jsonify({
            'success': True,
            'audio_data': audio_data.hex()  # Convert to hex string for JSON
        })
    except Exception as e:
        logger.error(f"ElevenLabs generation error: {e}")
        raise ElevenLabsError(f"Generation failed: {str(e)}")

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'revoice',
        'timestamp': time.time(),
        'active_sessions': len(video_sessions),
        'debug_mode': DEBUG
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5679, debug=DEBUG)
